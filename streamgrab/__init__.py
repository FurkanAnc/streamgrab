"""StreamGrab — 64-bit, modern bir video indirici iskeleti.

Mimari:
    UI (PySide6)  ->  DownloadManager  ->  harici motor (yt-dlp)  ->  ffmpeg

Motor tanimlari `app/engines/*.json` icinde bildirimsel olarak tutulur;
kodda site/extractor mantigi yoktur.
"""

__version__ = "0.2.0"
