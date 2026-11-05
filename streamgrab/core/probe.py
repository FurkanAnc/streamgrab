"""URL -> medya bilgisi (baslik, sure, format listesi).

Ekran ciktisi parse etmek yerine yt-dlp'ye `--dump-single-json` ile makine
tarafindan okunabilir JSON bastiriyoruz. Kirilganlik farki burada buyuk.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ..engines.loader import Engine
from .runner import run_capture


UNAVAILABLE_TITLES = ("[Private video]", "[Deleted video]", "[Unavailable]")


class ProbeError(RuntimeError):
    pass


@dataclass
class FormatInfo:
    format_id: str
    ext: str = ""
    height: int = 0
    width: int = 0
    vcodec: str = ""
    acodec: str = ""
    filesize: int = 0
    tbr: float = 0.0
    note: str = ""
    protocol: str = ""

    @property
    def has_video(self) -> bool:
        return self.vcodec not in ("", "none")

    @property
    def has_audio(self) -> bool:
        return self.acodec not in ("", "none")

    @property
    def resolution(self) -> str:
        if self.height:
            return f"{self.height}p" + (" (HDR)" if "hdr" in self.note.lower() else "")
        return "ses" if self.has_audio and not self.has_video else "-"


@dataclass
class PlaylistEntry:
    index: int
    id: str
    title: str
    url: str
    duration: int = 0
    uploader: str = ""
    extractor: str = ""
    available: bool = True


@dataclass
class MediaInfo:
    url: str
    title: str
    uploader: str = ""
    duration: int = 0
    thumbnail: str = ""
    extractor: str = ""
    formats: list[FormatInfo] = field(default_factory=list)
    id: str = ""
    is_playlist: bool = False
    entries: list[PlaylistEntry] = field(default_factory=list)

    def best_audio(self) -> FormatInfo | None:
        audio = [f for f in self.formats if f.has_audio and not f.has_video]
        if not audio:
            return None
        return max(audio, key=lambda f: (f.tbr or 0, f.filesize or 0))


def _parse_json(text: str) -> dict[str, Any]:
    # yt-dlp bazi durumlarda JSON'dan once uyari satiri basabilir.
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    raise ProbeError("Motordan gecerli JSON alinamadi.")


def _collect_entries(data: dict[str, Any]) -> list[PlaylistEntry]:
    """Duz liste uretir. Kanal koku sekmeleri (Videos/Shorts) ic ice liste doner."""
    entries: list[PlaylistEntry] = []
    seen: set[str] = set()

    def walk(items: list[Any], extractor: str) -> None:
        for raw in items or []:
            if not isinstance(raw, dict):
                continue
            nested = raw.get("entries")
            if nested is not None:
                walk(nested, raw.get("extractor_key") or extractor)
                continue

            url = raw.get("webpage_url") or raw.get("url") or ""
            if not str(url).lower().startswith(("http://", "https://")):
                continue
            video_id = str(raw.get("id") or url)
            if video_id in seen:
                continue
            seen.add(video_id)

            title = raw.get("title") or ""
            # Gizli/silinmis videolarin basligi gelmez ya da yer tutucudur.
            hidden = not title or title in UNAVAILABLE_TITLES
            entries.append(
                PlaylistEntry(
                    index=len(entries) + 1,
                    id=video_id,
                    title=title or "(başlık alınamadı)",
                    url=url,
                    duration=int(raw.get("duration") or 0),
                    uploader=raw.get("uploader") or raw.get("channel") or "",
                    extractor=raw.get("ie_key") or raw.get("extractor_key") or extractor,
                    available=not hidden,
                )
            )

    walk(data.get("entries") or [], data.get("extractor_key") or "")
    return entries


def _thumbnail(data: dict[str, Any]) -> str:
    if data.get("thumbnail"):
        return data["thumbnail"]
    thumbnails = [t for t in data.get("thumbnails") or [] if isinstance(t, dict) and t.get("url")]
    return thumbnails[-1]["url"] if thumbnails else ""


def _normalize(data: dict[str, Any], url: str) -> MediaInfo:
    is_playlist = data.get("_type") in ("playlist", "multi_video") or "entries" in data

    formats: list[FormatInfo] = []
    for raw in data.get("formats") or []:
        if not isinstance(raw, dict):
            continue
        size = raw.get("filesize") or raw.get("filesize_approx") or 0
        formats.append(
            FormatInfo(
                format_id=str(raw.get("format_id", "")),
                ext=raw.get("ext") or "",
                height=int(raw.get("height") or 0),
                width=int(raw.get("width") or 0),
                vcodec=raw.get("vcodec") or "",
                acodec=raw.get("acodec") or "",
                filesize=int(size or 0),
                tbr=float(raw.get("tbr") or 0),
                note=raw.get("format_note") or "",
                protocol=raw.get("protocol") or "",
            )
        )

    formats.sort(key=lambda f: (f.height, f.tbr, f.filesize), reverse=True)

    return MediaInfo(
        url=data.get("webpage_url") or url,
        title=data.get("title") or "(basliksiz)",
        uploader=data.get("uploader") or data.get("channel") or "",
        duration=int(data.get("duration") or 0),
        thumbnail=_thumbnail(data),
        extractor=data.get("extractor_key") or data.get("extractor") or "",
        formats=formats,
        id=str(data.get("id") or ""),
        is_playlist=is_playlist,
        entries=_collect_entries(data) if is_playlist else [],
    )


def probe(
    engine: Engine,
    url: str,
    cookies: str = "",
    timeout: float = 300,
    single: bool = False,
) -> MediaInfo:
    if engine.source == "missing":
        raise ProbeError(
            "yt-dlp bulunamadı. Ayarlar → Araçlar bölümünden kurabilirsin."
        )

    code, output = run_capture(engine.probe_command(url, cookies, single=single), timeout=timeout)
    if "ERROR:" in output and code != 0:
        message = next(
            (line.split("ERROR:", 1)[1].strip() for line in output.splitlines() if "ERROR:" in line),
            "bilinmeyen hata",
        )
        raise ProbeError(message)
    if not output.strip():
        raise ProbeError("Motor bos cikti dondurdu.")

    try:
        data = _parse_json(output)
    except ProbeError:
        tail = "\n".join(output.strip().splitlines()[-5:])
        raise ProbeError(f"JSON cozulemedi. Son cikti:\n{tail}") from None

    return _normalize(data, url)
