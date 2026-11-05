"""Arayuzde kullanilan kucuk formatlama yardimcilari."""

from __future__ import annotations


def human_size(value: float) -> str:
    if not value or value <= 0:
        return "-"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)
    index = 0
    while size >= 1024 and index < len(units) - 1:
        size /= 1024.0
        index += 1
    if index == 0:
        return f"{int(size)}{units[index]}"
    return f"{size:.1f} {units[index]}"


def human_speed(value: float) -> str:
    if not value or value <= 0:
        return ""
    return f"{human_size(value)}/s"


def human_duration(seconds: float) -> str:
    seconds = int(seconds or 0)
    if seconds <= 0:
        return ""
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def human_eta(seconds: float) -> str:
    if not seconds or seconds <= 0:
        return ""
    return human_duration(seconds)
