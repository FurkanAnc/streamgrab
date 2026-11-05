"""Basit JSON tabanli ayar deposu (QSettings'e bagimli degil)."""

from __future__ import annotations

import json
from typing import Any

from .paths import default_download_dir, settings_file

DEFAULTS: dict[str, Any] = {
    "download_dir": str(default_download_dir()),
    "max_concurrent": 4,
    "cookies_browser": "",
    "ffmpeg_path": "",
    "aria2_path": "",
    "merge_format": "mp4",
    "write_subs": False,
    "embed_metadata": True,
    "engine": "yt-dlp",
    "last_preset": 0,
    "concurrent_fragments": 8,
    "external_downloader": "auto",  # auto | native | aria2
    "http_chunk_size": "",
    "throttled_rate": True,
    "use_archive": True,
    "auto_retry": 3,
    "resume_on_start": True,
    "playlist_subfolder": True,
    "setup_dismissed": False,
}


class Config:
    def __init__(self, values: dict[str, Any] | None = None) -> None:
        self._values = dict(DEFAULTS)
        if values:
            self._values.update({k: v for k, v in values.items() if k in DEFAULTS})

    # ---------------------------------------------------------------- okuma
    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, DEFAULTS.get(key, default))

    def set(self, key: str, value: Any) -> None:
        self._values[key] = value

    def update(self, values: dict[str, Any]) -> None:
        for key, value in values.items():
            if key in DEFAULTS:
                self._values[key] = value

    def as_dict(self) -> dict[str, Any]:
        return dict(self._values)

    # --------------------------------------------------------------- disk
    @classmethod
    def load(cls) -> "Config":
        path = settings_file()
        if not path.exists():
            return cls()
        try:
            with path.open("r", encoding="utf-8") as handle:
                return cls(json.load(handle))
        except (OSError, ValueError):
            # Bozuk ayar dosyasi uygulamayi kilitlemesin.
            return cls()

    def save(self) -> None:
        path = settings_file()
        tmp = path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(self._values, handle, ensure_ascii=False, indent=2)
        tmp.replace(path)
