"""Kalici veriler: kuyruk, indirme gecmisi ve yt-dlp arsivi.

Hepsi %APPDATA%\\StreamGrab altinda duz dosyadir. Bozuk bir dosya uygulamayi
kilitlememeli; bu yuzden okuma hatalari bos sonuc doner.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from ..paths import archive_file, history_file, queue_file


# ------------------------------------------------------------------ kuyruk
def save_queue(records: Iterable[dict[str, Any]]) -> None:
    path = queue_file()
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(list(records), handle, ensure_ascii=False)
    tmp.replace(path)


def load_queue() -> list[dict[str, Any]]:
    try:
        with queue_file().open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []


# ------------------------------------------------------------------ gecmis
def append_history(record: dict[str, Any]) -> None:
    with history_file().open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_history() -> list[dict[str, Any]]:
    """Yeniden eskiye siralar; bozuk satirlari atlar."""
    records: list[dict[str, Any]] = []
    try:
        with history_file().open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    value = json.loads(line)
                except ValueError:
                    continue
                if isinstance(value, dict):
                    records.append(value)
    except OSError:
        return []
    records.reverse()
    return records


def clear_history() -> None:
    history_file().unlink(missing_ok=True)


# ------------------------------------------------------------------- arsiv
def archive_key(extractor: str, video_id: str) -> str:
    """yt-dlp'nin --download-archive dosyasindaki satir bicimi."""
    return f"{extractor.lower()} {video_id}"


def archive_keys() -> set[str]:
    try:
        with archive_file().open("r", encoding="utf-8") as handle:
            return {line.strip() for line in handle if line.strip()}
    except OSError:
        return set()


def clear_archive() -> None:
    archive_file().unlink(missing_ok=True)
