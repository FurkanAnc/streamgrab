"""Motor ve yardimci arac indirme (uygulamadan bagimsiz).

Siteler degistiginde tek guncellenmesi gereken sey yt-dlp'dir; uygulamanin
kendisini yeniden dagitmaya gerek kalmaz. Bu yuzden motor ayri yasam dongusune
sahip olmali.

Indirilen exe'ler dogrudan calistirilacagi icin yayimlanan SHA-256 degeriyle
dogrulanir. Eslesmezse dosya hedefe tasinmaz.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

from ..paths import bin_dir

USER_AGENT = "StreamGrab/0.2 (+https://github.com/mhogomchungu/media-downloader-inspired)"
CHUNK = 256 * 1024

Progress = Callable[[int, int], None] | None

YTDLP_API = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
DENO_API = "https://api.github.com/repos/denoland/deno/releases/latest"
DENO_ZIP = "deno-x86_64-pc-windows-msvc.zip"
FFMPEG_BASE = "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/"
FFMPEG_ZIP = "ffmpeg-master-latest-win64-gpl.zip"
ARIA2_ZIP = (
    "https://github.com/aria2/aria2/releases/download/release-1.37.0/"
    "aria2-1.37.0-win-64bit-build1.zip"
)


class UpdateError(RuntimeError):
    pass


# ------------------------------------------------------------------ ag
def _request(url: str, accept: str = "") -> urllib.request.Request:
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    return urllib.request.Request(url, headers=headers)


def _get_text(url: str, timeout: float = 30) -> str:
    try:
        with urllib.request.urlopen(_request(url), timeout=timeout) as response:
            return response.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as exc:
        raise UpdateError(f"Bağlantı kurulamadı: {exc}") from exc


def _get_json(url: str, timeout: float = 30) -> dict:
    request = _request(url, "application/vnd.github+json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise UpdateError(f"Sürüm bilgisi alınamadı: {exc}") from exc


def _fetch(url: str, target: Path, progress: Progress = None) -> str:
    """Dosyayi `target`a indirir, SHA-256 ozetini dondurur."""
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(_request(url), timeout=60) as response, target.open("wb") as handle:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = response.read(CHUNK)
                if not chunk:
                    break
                handle.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    except (urllib.error.URLError, OSError) as exc:
        target.unlink(missing_ok=True)
        raise UpdateError(f"İndirme başarısız: {exc}") from exc
    return digest.hexdigest()


# ------------------------------------------------------------ dogrulama
def expected_hash(checksums: str, filename: str) -> str:
    """Ozet dosyasindan `filename`in SHA-256 degerini bulur.

    "hash  dosya" satirlari ya da tek dosyalik .sha256sum bicimleri desteklenir.
    """
    pattern = re.compile(r"\b[0-9a-fA-F]{64}\b")
    for line in checksums.splitlines():
        found = pattern.search(line)
        if found and line.replace("*", " ").split()[-1] == filename:
            return found.group(0).lower()
    hashes = pattern.findall(checksums)
    if len(hashes) == 1:
        return hashes[0].lower()
    raise UpdateError(f"{filename} için doğrulama özeti bulunamadı.")


def _verify(actual: str, expected: str, path: Path) -> None:
    if actual.lower() != expected.lower():
        path.unlink(missing_ok=True)
        raise UpdateError(f"{path.name} doğrulanamadı: SHA-256 özeti eşleşmiyor.")


def _install(source: Path, target: Path) -> None:
    try:
        os.replace(source, target)
    except OSError as exc:
        source.unlink(missing_ok=True)
        raise UpdateError(f"{target.name} yazılamadı (kullanımda olabilir): {exc}") from exc


def _extract(archive: Path, names: list[str]) -> list[Path]:
    """Arsivden dosya adina gore ceker ve bin/ klasorune koyar."""
    installed: list[Path] = []
    try:
        with zipfile.ZipFile(archive) as bundle:
            for name in names:
                member = next((m for m in bundle.namelist() if m.rsplit("/", 1)[-1] == name), None)
                if member is None:
                    raise UpdateError(f"Arşivde {name} bulunamadı.")
                tmp = bin_dir() / f"{name}.tmp"
                with bundle.open(member) as source, tmp.open("wb") as destination:
                    shutil.copyfileobj(source, destination)
                target = bin_dir() / name
                _install(tmp, target)
                installed.append(target)
    except (zipfile.BadZipFile, OSError) as exc:
        raise UpdateError(f"Arşiv açılamadı: {exc}") from exc
    finally:
        archive.unlink(missing_ok=True)
    return installed


def _release_assets(api: str) -> tuple[str, dict[str, str]]:
    data = _get_json(api)
    assets = {a.get("name", ""): a.get("browser_download_url", "") for a in data.get("assets") or []}
    return str(data.get("tag_name", "?")), assets


# -------------------------------------------------------------- araclar
def download_ytdlp(progress: Progress = None, release_api: str = YTDLP_API) -> Path:
    tag, assets = _release_assets(release_api)
    if "yt-dlp.exe" not in assets or "SHA2-256SUMS" not in assets:
        raise UpdateError("Sürümde yt-dlp.exe veya özet dosyası bulunamadı.")
    expected = expected_hash(_get_text(assets["SHA2-256SUMS"]), "yt-dlp.exe")

    target = bin_dir() / "yt-dlp.exe"
    tmp = target.with_suffix(".exe.tmp")
    _verify(_fetch(assets["yt-dlp.exe"], tmp, progress), expected, tmp)
    _install(tmp, target)
    (bin_dir() / "VERSION").write_text(tag, encoding="utf-8")
    return target


def download_ffmpeg(progress: Progress = None) -> Path:
    expected = expected_hash(_get_text(FFMPEG_BASE + "checksums.sha256"), FFMPEG_ZIP)
    archive = bin_dir() / "ffmpeg-download.zip"
    _verify(_fetch(FFMPEG_BASE + FFMPEG_ZIP, archive, progress), expected, archive)
    return _extract(archive, ["ffmpeg.exe", "ffprobe.exe"])[0]


def download_deno(progress: Progress = None) -> Path:
    """YouTube'un JS korumalarini cozmek icin yt-dlp'nin kullandigi calisma ortami."""
    _tag, assets = _release_assets(DENO_API)
    checksum = f"{DENO_ZIP}.sha256sum"
    if DENO_ZIP not in assets or checksum not in assets:
        raise UpdateError("Sürümde deno veya özet dosyası bulunamadı.")
    expected = expected_hash(_get_text(assets[checksum]), DENO_ZIP)
    archive = bin_dir() / "deno-download.zip"
    _verify(_fetch(assets[DENO_ZIP], archive, progress), expected, archive)
    return _extract(archive, ["deno.exe"])[0]


def download_aria2(progress: Progress = None) -> Path:
    """aria2c.exe'yi resmi surum zip'inden cikarip bin/ klasorune koyar."""
    archive = bin_dir() / "aria2-download.zip"
    _fetch(ARIA2_ZIP, archive, progress)
    return _extract(archive, ["aria2c.exe"])[0]


DOWNLOADERS = {
    "yt-dlp": download_ytdlp,
    "ffmpeg": download_ffmpeg,
    "deno": download_deno,
    "aria2": download_aria2,
}
