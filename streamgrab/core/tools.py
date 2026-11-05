"""ffmpeg gibi yardimci araclarin yerini bulur."""

from __future__ import annotations

import shutil
from pathlib import Path

from ..paths import bin_dir


def _search_candidates(configured: str) -> list[Path]:
    candidates: list[Path] = []
    if configured:
        path = Path(configured)
        candidates.append(path)
        if path.is_dir():
            candidates.append(path / ("ffmpeg.exe" if path.drive else "ffmpeg"))
    candidates.append(bin_dir() / "ffmpeg.exe")
    candidates.append(bin_dir() / "ffmpeg" / "ffmpeg.exe")
    return candidates


def find_ffmpeg(configured: str = "") -> str:
    """ffmpeg.exe'nin bulundugu klasoru dondurur; bulunamazsa bos string."""
    for candidate in _search_candidates(configured):
        try:
            if candidate.is_file():
                if candidate.is_dir():
                    continue
                return str(candidate.parent)
        except OSError:
            continue

    found = shutil.which("ffmpeg")
    if found:
        return str(Path(found).parent)
    return ""


def find_ffmpeg_exe(configured: str = "") -> str:
    directory = find_ffmpeg(configured)
    if not directory:
        return ""
    exe = Path(directory) / ("ffmpeg.exe" if (Path(directory) / "ffmpeg.exe").exists() else "ffmpeg")
    return str(exe)


def ffmpeg_version(configured: str = "") -> str:
    exe = find_ffmpeg_exe(configured)
    if not exe:
        return ""
    from .runner import run_capture

    code, out = run_capture([exe, "-version"], timeout=20)
    if code != 0:
        return ""
    first = out.splitlines()[0] if out.splitlines() else ""
    # "ffmpeg version 9.0.1-full_build-www.gyan.dev ..." -> "9.0.1"
    parts = first.split()
    if len(parts) >= 3:
        return parts[2].split("-")[0]
    return first


def find_aria2(configured: str = "") -> str:
    """aria2c.exe'nin tam yolunu dondurur; yoksa bos string.

    aria2, duz http(s) dosyalarini Range istekleriyle paralel ceker; HLS/DASH
    parcalarinda ise yt-dlp'nin kendi indiricisi (--concurrent-fragments) kullanilir.
    """
    candidates: list[Path] = []
    if configured:
        path = Path(configured)
        candidates.append(path if path.suffix else path / "aria2c.exe")
        candidates.append(path)
    candidates.append(bin_dir() / "aria2c.exe")
    candidates.append(bin_dir() / "aria2" / "aria2c.exe")

    for candidate in candidates:
        try:
            if candidate.is_file():
                return str(candidate)
        except OSError:
            continue

    found = shutil.which("aria2c") or shutil.which("aria2c.exe")
    return found or ""


def find_deno() -> str:
    """deno.exe'nin tam yolu; yoksa bos string."""
    candidate = bin_dir() / "deno.exe"
    if candidate.is_file():
        return str(candidate)
    return shutil.which("deno") or ""


def find_js_runtime() -> str:
    """yt-dlp'nin YouTube icin istedigi JS ortami: "deno:yol", "node:yol" veya "".

    yt-dlp varsayilan olarak sadece deno'yu arar; node'u acikca belirtmek gerekir.
    """
    deno = find_deno()
    if deno:
        return f"deno:{deno}"
    node = shutil.which("node")
    return f"node:{node}" if node else ""


def missing_tools(engine, ffmpeg_path: str = "") -> list[str]:
    """Ilk acilis kurulumunun indirmesi gerekenler: yt-dlp / ffmpeg / deno."""
    missing: list[str] = []
    if engine is None or engine.source == "missing":
        missing.append("yt-dlp")
    if not find_ffmpeg(ffmpeg_path):
        missing.append("ffmpeg")
    if not find_js_runtime():
        missing.append("deno")
    return missing


def aria2_version(exe: str) -> str:
    if not exe:
        return ""
    from .runner import run_capture

    code, out = run_capture([exe, "--version"], timeout=20)
    if code != 0 or not out.strip():
        return ""
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    # Ilk satir "aria2 version 1.37.0" seklinde.
    for line in lines[:3]:
        if "version" in line.lower():
            return line.split()[-1]
    return lines[0]
