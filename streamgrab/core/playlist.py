"""Oynatma listesi icin kucuk yardimcilar (arayuzden bagimsiz)."""

from __future__ import annotations

import re

_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def parse_ranges(text: str, maximum: int) -> set[int]:
    """"1-5, 8, 12-" gibi bir ifadeyi 1 tabanli sira numaralarina cevirir.

    Gecersiz parcalar ValueError atar; liste disina tasan numaralar kirpilir.
    """
    result: set[int] = set()
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        match = re.fullmatch(r"(\d*)\s*-\s*(\d*)|(\d+)", part)
        if not match or part == "-":
            raise ValueError(part)
        if match.group(3):
            start = end = int(match.group(3))
        else:
            start = int(match.group(1) or 1)
            end = int(match.group(2) or maximum)
        if start > end:
            raise ValueError(part)
        result.update(range(max(1, start), min(end, maximum) + 1))
    return result


def safe_folder_name(name: str, fallback: str = "Oynatma listesi") -> str:
    """Liste basligini Windows'ta gecerli bir klasor adina cevirir."""
    cleaned = _ILLEGAL.sub(" ", name or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")[:100].strip(" .")
    if not cleaned or cleaned.upper() in _RESERVED:
        return fallback
    return cleaned
