"""Indirme kuyrugu: en fazla N es zamanli yt-dlp sureci.

Her is bir alt surec; iptal veya duraklatma = surec agacini oldurmek. Duraklatilan
is yeniden baslatildiginda yt-dlp yarim kalan .part dosyasindan devam eder.

Kuyruk, Qt sinyalleri uzerinden arayuzu bilgilendirir; sinyaller worker
thread'den emit edilir ve Qt bunlari ana thread'e kuyruklar.
"""

from __future__ import annotations

import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field, fields
from typing import Any, Iterable

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from ..config import Config
from ..engines.loader import Engine
from . import runner, store
from .errors import explain

_ARIA2_PERCENT = re.compile(r"\((\d+)%\)")
_ARIA2_SIZE = re.compile(r"([\d.]+)([KMGT]?i?B)/([\d.]+)([KMGT]?i?B)")
_ARIA2_SPEED = re.compile(r"DL:([\d.]+)([KMGT]?i?B)")

_UNITS = {
    "B": 1,
    "KIB": 1024,
    "MIB": 1024**2,
    "GIB": 1024**3,
    "TIB": 1024**4,
    "KB": 1000,
    "MB": 1000**2,
    "GB": 1000**3,
    "TB": 1000**4,
}

RETRY_DELAYS = (5, 15, 45)  # saniye; deneme sayisi bunu asarsa son deger kullanilir
SAVE_INTERVAL_MS = 3000

# Diske yazilmayan, yalnizca calisma anina ait alanlar.
_TRANSIENT_FIELDS = {"lines", "speed", "eta"}
_UNFINISHED = ("queued", "downloading", "merging", "waiting")


def _to_bytes(value: str, unit: str) -> float:
    try:
        return float(value) * _UNITS.get(unit.upper(), 1)
    except (TypeError, ValueError):
        return 0.0


@dataclass
class Job:
    url: str
    title: str
    selector: str
    outdir: str
    audio_only: bool = False
    cookies: str = ""
    ffmpeg_dir: str = ""
    merge_format: str = "mp4"
    write_subs: bool = False
    embed_metadata: bool = True
    fragments: int = 1
    aria2_exe: str = ""
    chunk_size: str = ""
    throttled_rate: bool = False
    archive_file: str = ""
    filename_prefix: str = ""
    format_sort: str = ""
    playlist: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    # queued | downloading | merging | paused | waiting | done | failed | canceled
    status: str = "queued"
    downloaded: float = 0.0
    total: float = 0.0
    speed: float = 0.0
    eta: float = 0.0
    filepath: str = ""
    error: str = ""
    lines: list[str] = field(default_factory=list)
    reported_percent: float = -1.0
    attempts: int = 0
    skipped: bool = False
    finished_at: float = 0.0

    @property
    def percent(self) -> float:
        if self.status == "done":
            return 100.0
        if self.reported_percent >= 0:
            return max(0.0, min(100.0, self.reported_percent))
        if self.total <= 0:
            return 0.0
        return max(0.0, min(100.0, self.downloaded / self.total * 100.0))


def job_to_dict(job: Job) -> dict[str, Any]:
    data = asdict(job)
    for name in _TRANSIENT_FIELDS:
        data.pop(name, None)
    return data


def job_from_dict(data: dict[str, Any]) -> Job | None:
    known = {f.name for f in fields(Job)} - _TRANSIENT_FIELDS
    try:
        return Job(**{key: value for key, value in data.items() if key in known})
    except TypeError:  # eksik zorunlu alan: eski/bozuk kayit
        return None


class _Worker(threading.Thread):
    def __init__(self, manager: "DownloadManager", job: Job, argv: list[str]) -> None:
        super().__init__(daemon=True, name=f"dl-{job.id}")
        self._manager = manager
        self._job = job
        self._argv = argv
        self._process = None
        self.stopped = False  # stop() sonrasi is durumuna bu thread dokunmaz

    @property
    def job(self) -> Job:
        return self._job

    def run(self) -> None:
        job = self._job
        manager = self._manager
        try:
            process = runner.hidden_popen(self._argv)
            self._process = process
            if self.stopped:  # surec olusmadan stop() cagrilmis olabilir
                runner.kill_tree(process)
            self._pump(process)
            code = process.wait()
        except OSError as exc:
            if not self.stopped:
                job.error = f"Surec baslatilamadi: {exc}"
                job.status = "failed"
            manager._worker_done.emit(self)
            return

        if self.stopped:
            manager._worker_done.emit(self)
            return

        if code == 0:
            job.status = "done"
            job.downloaded = job.total or job.downloaded
            if not job.total:
                job.total = 0
        else:
            job.status = "failed"
            if not job.error:
                tail = [line for line in job.lines if line.strip()][-3:]
                job.error = tail[-1] if tail else f"yt-dlp {code} koduyla cikti."
        manager._worker_done.emit(self)

    def _pump(self, process) -> None:
        job = self._job
        manager = self._manager
        marker = manager.engine.progress_marker
        assert process.stdout is not None
        for raw in process.stdout:
            if self.stopped:
                break
            line = raw.rstrip("\r\n")
            if not line:
                continue
            if marker in line:
                self._apply_progress(line.split(marker, 1)[1])
                manager.changed.emit(job.id)
                continue
            if "[#" in line and "CN:" in line:
                self._apply_aria2_progress(line)
                manager.changed.emit(job.id)
                continue
            self._track(line)
            job.lines.append(line)
            if len(job.lines) > 400:
                del job.lines[:100]
            manager.line.emit(job.id, line)

    def _apply_progress(self, payload: str) -> None:
        parts = payload.split(";")
        if len(parts) < 5:
            return

        def number(value: str) -> float:
            value = value.strip()
            if not value or value.upper() in ("NA", "N/A", "NONE"):
                return 0.0
            try:
                return float(value)
            except ValueError:
                return 0.0

        job = self._job
        downloaded = number(parts[0])
        total = number(parts[1]) or number(parts[2])
        speed = number(parts[3])
        eta = number(parts[4])

        job.downloaded = downloaded or job.downloaded
        if total:
            job.total = total
        if speed > 0:
            job.speed = speed
        job.eta = eta
        if job.status != "downloading" and not self.stopped:
            job.status = "downloading"

    def _apply_aria2_progress(self, line: str) -> None:
        """Harici indirici (aria2) cikti satiri:
        [#2089b0 1.0MiB/1.0MiB(99%) CN:1 DL:1.0MiB ETA:0s]
        """
        job = self._job
        percent = _ARIA2_PERCENT.search(line)
        size = _ARIA2_SIZE.search(line)
        speed = _ARIA2_SPEED.search(line)

        if percent:
            job.reported_percent = float(percent.group(1))
        if size:
            job.downloaded = _to_bytes(size.group(1), size.group(2))
            job.total = _to_bytes(size.group(3), size.group(4))
        if speed:
            job.speed = _to_bytes(speed.group(1), speed.group(2))
        if job.status != "downloading" and not self.stopped:
            job.status = "downloading"

    def _track(self, line: str) -> None:
        job = self._job
        for prefix in (
            "[Merger] Merging formats into ",
            "[ExtractAudio] Destination: ",
            "[download] Destination: ",
        ):
            if line.startswith(prefix):
                job.filepath = line[len(prefix) :].strip().strip('"')
                if prefix.startswith("[Merger]"):
                    job.status = "merging"
                return
        if line.endswith("has already been downloaded"):
            job.filepath = line[len("[download] ") : -len(" has already been downloaded")].strip()
            return
        if line.endswith("has already been recorded in the archive"):
            job.skipped = True
            return
        if line.startswith("ERROR:"):
            job.error = line[len("ERROR:") :].strip()

    def stop(self) -> None:
        """Sureci oldurur; thread sonlaninca is durumunu degistirmez."""
        self.stopped = True
        runner.kill_tree(self._process)


class DownloadManager(QObject):
    changed = Signal(str)
    finished = Signal(str)
    line = Signal(str, str)
    _worker_done = Signal(object)

    def __init__(self, config: Config, engine: Engine, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.engine = engine
        self.jobs: dict[str, Job] = {}
        self.order: list[str] = []
        self._active: dict[str, _Worker] = {}
        self._closing = False

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(SAVE_INTERVAL_MS)
        self._save_timer.timeout.connect(self.save)
        self.changed.connect(self._schedule_save)
        self._worker_done.connect(self._on_worker_done)

    # ------------------------------------------------------------- kuyruk
    def add(self, job: Job, at_top: bool = True) -> Job:
        self.jobs[job.id] = job
        if at_top:
            self.order.insert(0, job.id)
        else:
            self.order.append(job.id)
        self.changed.emit(job.id)
        self._pump()
        return job

    def add_many(self, jobs: list[Job]) -> None:
        """Isleri verilen sirayla kuyrugun basina ekler (ilki once baslar)."""
        for job in jobs:
            self.jobs[job.id] = job
        self.order[0:0] = [job.id for job in jobs]
        for job in jobs:
            self.changed.emit(job.id)
        self._pump()

    def cancel(self, job_id: str) -> None:
        job = self.jobs.get(job_id)
        if not job or job.status in ("done", "failed", "canceled"):
            return
        self._stop_worker(job_id)
        job.status = "canceled"
        self.changed.emit(job_id)
        self._pump()

    def cancel_all(self) -> None:
        for job_id in list(self.order):
            self.cancel(job_id)

    def pause(self, job_id: str) -> None:
        job = self.jobs.get(job_id)
        if not job or job.status not in ("queued", "waiting", "downloading"):
            return
        self._stop_worker(job_id)
        job.status = "paused"
        job.speed = 0.0
        job.eta = 0.0
        self.changed.emit(job_id)
        self._pump()

    def pause_all(self) -> None:
        for job_id in list(self.order):
            self.pause(job_id)

    def resume(self, job_id: str) -> None:
        """Duraklatilan, basarisiz veya iptal edilen isi yeniden kuyruga alir."""
        job = self.jobs.get(job_id)
        if not job or job.status not in ("paused", "failed", "canceled"):
            return
        job.status = "queued"
        job.attempts = 0
        job.error = ""
        self.changed.emit(job_id)
        self._pump()

    def resume_all(self) -> None:
        for job_id in list(self.order):
            if self.jobs[job_id].status == "paused":
                self.resume(job_id)

    def remove_finished(self) -> list[str]:
        """Bitmis/iptal isleri listeden atar. Basarisizlar tekrar denenebilsin diye kalir."""
        removed = [i for i in self.order if self.jobs[i].status in ("done", "canceled")]
        for job_id in removed:
            self.order.remove(job_id)
            del self.jobs[job_id]
        self.save()
        return removed

    def active_count(self) -> int:
        return len(self._active)

    def _stop_worker(self, job_id: str) -> None:
        worker = self._active.pop(job_id, None)
        if worker:
            worker.stop()

    # ------------------------------------------------------------ calisma
    def start(self) -> None:
        self._pump()

    def _pump(self) -> None:
        if self._closing or self.engine.source == "missing":
            return
        limit = max(1, int(self.config.get("max_concurrent", 4)))
        for job_id in self.order:
            if len(self._active) >= limit:
                break
            if job_id in self._active:
                continue
            job = self.jobs[job_id]
            if job.status != "queued":
                continue
            self._start(job)

    def _start(self, job: Job) -> None:
        argv = self.engine.download_command(
            job.url,
            job.outdir,
            job.selector,
            cookies=job.cookies,
            ffmpeg_dir=job.ffmpeg_dir,
            audio_only=job.audio_only,
            merge_format=job.merge_format,
            write_subs=job.write_subs,
            embed_metadata=job.embed_metadata,
            fragments=job.fragments,
            aria2_exe=job.aria2_exe,
            chunk_size=job.chunk_size,
            throttled_rate=job.throttled_rate,
            archive_file=job.archive_file,
            filename_prefix=job.filename_prefix,
            format_sort=job.format_sort,
        )
        job.status = "downloading"
        job.error = ""
        job.speed = 0.0
        job.eta = 0.0
        job.reported_percent = -1.0
        job.lines.append("$ " + " ".join(argv))
        worker = _Worker(self, job, argv)
        self._active[job.id] = worker
        worker.start()
        self.changed.emit(job.id)

    @Slot(object)
    def _on_worker_done(self, worker: _Worker) -> None:
        job = worker.job
        # Durdurulan is bu arada yeniden baslamis olabilir; yeni worker'a dokunma.
        if self._active.get(job.id) is worker:
            del self._active[job.id]

        if not worker.stopped:
            if job.status == "done":
                self._record_done(job)
                self.finished.emit(job.id)
            elif job.status == "failed" and not self._schedule_retry(job):
                self.finished.emit(job.id)

        self.changed.emit(job.id)
        self._pump()

    def _record_done(self, job: Job) -> None:
        job.finished_at = time.time()
        if job.skipped:
            return
        store.append_history(
            {
                "time": job.finished_at,
                "title": job.title,
                "url": job.url,
                "path": job.filepath,
                "playlist": job.playlist,
                "size": job.total,
            }
        )

    def _schedule_retry(self, job: Job) -> bool:
        limit = int(self.config.get("auto_retry", 0) or 0)
        if self._closing or job.attempts >= limit or not explain(job.error).retryable:
            return False
        delay = RETRY_DELAYS[min(job.attempts, len(RETRY_DELAYS) - 1)]
        job.attempts += 1
        job.status = "waiting"
        attempt = job.attempts
        QTimer.singleShot(int(delay * 1000), self, lambda: self._retry_due(job.id, attempt))
        return True

    def _retry_due(self, job_id: str, attempt: int) -> None:
        job = self.jobs.get(job_id)
        # Beklerken duraklatilmis/iptal edilmis olabilir.
        if job and job.status == "waiting" and job.attempts == attempt:
            job.status = "queued"
            self.changed.emit(job_id)
            self._pump()

    # ---------------------------------------------------------- kalicilik
    @Slot(str)
    def _schedule_save(self, _job_id: str = "") -> None:
        if not self._closing and not self._save_timer.isActive():
            self._save_timer.start()

    def save(self) -> None:
        try:
            store.save_queue(job_to_dict(self.jobs[job_id]) for job_id in self.order)
        except OSError:
            pass  # bir sonraki kayitta tekrar denenir

    def restore(self, records: Iterable[dict[str, Any]], autostart: bool = True) -> list[Job]:
        """Onceki oturumun islerini yukler; baslatmak icin start() cagrilir."""
        restored: list[Job] = []
        for record in records:
            job = job_from_dict(record)
            if job is None or job.id in self.jobs:
                continue
            if job.status in _UNFINISHED:
                job.status = "queued" if autostart else "paused"
            self.jobs[job.id] = job
            self.order.append(job.id)
            restored.append(job)
        return restored

    def shutdown(self) -> None:
        """Uygulama kapanirken: calisan isleri durdurur, sonraki acilisa birakir."""
        self._closing = True
        self._save_timer.stop()
        workers = list(self._active.values())
        self._active.clear()
        for worker in workers:
            worker.stop()
            worker.job.status = "queued"
        for worker in workers:
            worker.join(3)
        self.save()

    # ----------------------------------------------------------- yardimci
    def jobs_in_order(self) -> Iterable[Job]:
        for job_id in self.order:
            yield self.jobs[job_id]
