"""Uygulamanin kullandigi yollar tek yerde toplanir."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "StreamGrab"


def is_frozen() -> bool:
    """PyInstaller ile paketlenmis exe olarak mi calisiyoruz?"""
    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    """Depo kok dizini (streamgrab/ klasorunun bir ustu)."""
    return Path(__file__).resolve().parent.parent


def package_dir() -> Path:
    return Path(__file__).resolve().parent


def bin_dir() -> Path:
    """Uygulamayla birlikte tasinan motor binary'leri (yt-dlp.exe, ffmpeg.exe...)."""
    if is_frozen():
        # Kurulum klasoru salt okunur sayilir; indirilen araclar kullanici profiline gider.
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local")
        path = Path(base) / APP_NAME / "bin"
    else:
        path = project_root() / "bin"
    path.mkdir(parents=True, exist_ok=True)
    return path


def engines_dir() -> Path:
    return package_dir() / "engines"


def assets_dir() -> Path:
    return package_dir() / "assets"


def app_data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_file() -> Path:
    return app_data_dir() / "settings.json"


def queue_file() -> Path:
    return app_data_dir() / "queue.json"


def history_file() -> Path:
    return app_data_dir() / "history.jsonl"


def archive_file() -> Path:
    return app_data_dir() / "archive.txt"


def lock_file() -> Path:
    return app_data_dir() / "instance.lock"


def log_file() -> Path:
    return app_data_dir() / "streamgrab.log"


def default_download_dir() -> Path:
    path = Path.home() / "Downloads" / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def python_exe() -> str:
    """yt-dlp'yi `python -m yt_dlp` olarak calistirmak icin kullanilir."""
    return sys.executable
