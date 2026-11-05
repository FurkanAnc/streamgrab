"""Kuyruk yasam dongusu: gercek alt surecler, sahte motor."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication

from streamgrab.config import Config
from streamgrab.core import downloader, store
from streamgrab.core.downloader import DownloadManager, Job, job_from_dict, job_to_dict
from streamgrab.engines.loader import Engine

FAKE = str(Path(__file__).with_name("fake_ytdlp.py"))


@pytest.fixture(scope="session")
def app():
    return QCoreApplication.instance() or QCoreApplication([])


@pytest.fixture
def manager(app, tmp_path, monkeypatch):
    monkeypatch.setattr(downloader, "RETRY_DELAYS", (0.01,))
    store.clear_history()
    spec = {"id": "fake", "progressMarker": "@@PROG@@"}
    engine = Engine(spec=spec, argv=[sys.executable, FAKE, str(tmp_path / "runs.log")], source="bundle")
    config = Config({"max_concurrent": 2, "auto_retry": 2})
    instance = DownloadManager(config, engine)
    yield instance
    instance.shutdown()


def job(url: str) -> Job:
    return Job(url=url, title=url, selector="b", outdir="C:/out")


def wait(condition, timeout: float = 15) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        QCoreApplication.processEvents()
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError("zaman asimi")


def test_download_finishes_and_goes_to_history(manager):
    item = manager.add(job("fake://ok"))
    wait(lambda: item.status == "done")
    assert item.filepath == "C:\\out\\ok.mp4"
    assert store.load_history()[0]["url"] == "fake://ok"


def test_archive_skip_is_done_but_not_in_history(manager):
    item = manager.add(job("fake://archive"))
    wait(lambda: item.status == "done")
    assert item.skipped
    assert store.load_history() == []


def test_transient_error_retries_then_succeeds(manager):
    item = manager.add(job("fake://flaky"))
    wait(lambda: item.status == "done")
    assert item.attempts == 1
    assert item.error == ""


def test_permanent_error_does_not_retry(manager):
    item = manager.add(job("fake://private"))
    wait(lambda: item.status == "failed" and manager.active_count() == 0)
    assert item.attempts == 0
    assert "Private video" in item.error


def test_retry_limit_is_respected(manager, tmp_path):
    manager.config.set("auto_retry", 0)
    item = manager.add(job("fake://flaky"))
    wait(lambda: item.status == "failed" and manager.active_count() == 0)
    assert item.attempts == 0


def test_pause_frees_slot_and_resume_restarts(manager, tmp_path):
    item = manager.add(job("fake://slow"))
    wait(lambda: item.downloaded > 0)

    manager.pause(item.id)
    assert item.status == "paused"
    assert manager.active_count() == 0

    # Eski worker'in gec gelen bildirimi yeni calismayi bozmamali.
    manager.resume(item.id)
    assert item.status == "downloading"
    time.sleep(0.2)
    QCoreApplication.processEvents()
    assert manager.active_count() == 1
    assert item.status == "downloading"

    manager.cancel(item.id)
    assert item.status == "canceled"
    wait(lambda: manager.active_count() == 0)
    time.sleep(0.2)
    QCoreApplication.processEvents()
    assert item.status == "canceled"


def test_pause_next_job_takes_the_slot(manager):
    first = manager.add(job("fake://slow"), at_top=False)
    second = manager.add(job("fake://slow"), at_top=False)
    third = manager.add(job("fake://ok"), at_top=False)
    assert third.status == "queued"
    manager.pause(first.id)
    wait(lambda: third.status == "done")
    manager.cancel(second.id)


def test_add_many_keeps_order(manager):
    jobs = [job("fake://slow"), job("fake://slow"), job("fake://slow")]
    manager.add_many(jobs)
    assert [j.id for j in manager.jobs_in_order()] == [j.id for j in jobs]
    assert [j.status for j in jobs] == ["downloading", "downloading", "queued"]
    manager.cancel_all()


def test_remove_finished_keeps_failed(manager):
    done = manager.add(job("fake://ok"))
    failed = manager.add(job("fake://private"))
    wait(lambda: done.status == "done" and failed.status == "failed")
    assert manager.remove_finished() == [done.id]
    assert failed.id in manager.jobs


def test_job_round_trip_drops_runtime_fields():
    item = job("http://x")
    item.lines.append("log")
    item.speed = 5.0
    data = job_to_dict(item)
    assert "lines" not in data and "speed" not in data
    assert job_from_dict(data).url == "http://x"
    assert job_from_dict({"title": "url yok"}) is None


def test_shutdown_requeues_active_jobs_and_restore_resumes(app, manager):
    running = manager.add(job("fake://slow"), at_top=False)
    second = manager.add(job("fake://slow"), at_top=False)
    paused = manager.add(job("fake://slow"), at_top=False)
    manager.pause(paused.id)
    wait(lambda: running.downloaded > 0)

    manager.shutdown()
    records = store.load_queue()
    assert [r["status"] for r in records] == ["queued", "queued", "paused"]

    fresh = DownloadManager(manager.config, manager.engine)
    restored = fresh.restore(records, autostart=True)
    assert [j.id for j in restored] == [running.id, second.id, paused.id]
    assert [j.status for j in restored] == ["queued", "queued", "paused"]
    fresh.start()
    assert fresh.active_count() == 2
    fresh.shutdown()


def test_restore_without_autostart_pauses(app, manager):
    record = job_to_dict(job("fake://ok"))
    record["status"] = "downloading"
    fresh = DownloadManager(manager.config, manager.engine)
    assert [j.status for j in fresh.restore([record], autostart=False)] == ["paused"]
    fresh._closing = True


def test_missing_engine_does_not_start_jobs(app, manager):
    manager.engine = Engine(spec={"id": "x"}, argv=["x"], source="missing")
    item = manager.add(job("fake://ok"))
    assert item.status == "queued"
    assert manager.active_count() == 0
