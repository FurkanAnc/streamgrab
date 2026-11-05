"""yt-dlp hata satirlarini anlasilir Turkce mesaja cevirir.

`retryable` otomatik yeniden denemeyi belirler: ag sorunu tekrar denenir, ama
"video gizli" gibi kalici bir hata tekrar denemekle duzelmez.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Explained:
    message: str
    retryable: bool


_RULES: list[tuple[str, str, bool]] = [
    (
        r"could not copy .*cookie database|cookie database",
        "Tarayıcı çerezleri okunamadı. Tarayıcıyı tamamen kapatıp tekrar dene.",
        False,
    ),
    (
        r"failed to decrypt with dpapi",
        "Bu tarayıcının çerezleri şifreli olduğu için okunamadı. "
        "Ayarlar'dan Firefox gibi başka bir tarayıcı seç.",
        False,
    ),
    (
        r"not a bot",
        "Site bot doğrulaması istiyor. Ayarlar'dan tarayıcı çerezlerini seçip tekrar dene.",
        False,
    ),
    (
        r"confirm your age|age[- ]restricted",
        "Yaş kısıtlamalı içerik. Ayarlar'dan giriş yaptığın tarayıcının çerezlerini seç.",
        False,
    ),
    (r"private video|video is private", "Bu video gizli.", False),
    (r"members[- ]only|join this channel", "Bu içerik yalnızca kanal üyelerine açık.", False),
    (r"\bdrm\b", "İçerik DRM korumalı; indirilemez.", False),
    (
        r"not available in your country|geo.?restrict",
        "Bu içerik bulunduğun ülkede erişime kapalı.",
        False,
    ),
    (r"premieres in|live event will begin|is upcoming", "Yayın henüz başlamadı.", False),
    (
        r"video unavailable|video is unavailable|this video is not available|has been removed|account .* terminated",
        "Video kaldırılmış ya da erişilemez durumda.",
        False,
    ),
    (
        r"requested format is not available",
        "Seçilen format bu video için yok. Başka bir kalite seç.",
        False,
    ),
    (r"unsupported url", "Bu site veya bağlantı desteklenmiyor.", False),
    (
        r"ffmpeg (is )?not (installed|found)|ffprobe .*not found",
        "ffmpeg bulunamadı. Ayarlar → Araçlar bölümünden kurabilirsin.",
        False,
    ),
    (r"no space left|errno 28|disk full", "Diskte yer kalmadı.", False),
    (
        r"permission denied|winerror 5\b|errno 13",
        "Dosyaya yazılamadı. Klasör izinlerini veya dosyanın açık olup olmadığını kontrol et.",
        False,
    ),
    (r"http error 429|too many requests", "Site çok fazla istek aldı ve geçici olarak engelledi.", True),
    (r"http error 403|forbidden", "Site isteği reddetti (403). yt-dlp'yi güncellemek çözebilir.", True),
    (r"http error 404", "İçerik sunucuda bulunamadı (404).", False),
    (r"http error 5\d\d", "Site geçici bir sunucu hatası verdi.", True),
    (
        r"timed? ?out|connection (reset|aborted|refused)|remote end closed|incompleteread"
        r"|getaddrinfo|name resolution|network is unreachable|unable to download",
        "Bağlantı sorunu oluştu.",
        True,
    ),
]

_COMPILED = [(re.compile(pattern, re.IGNORECASE), message, retry) for pattern, message, retry in _RULES]


def explain(raw: str) -> Explained:
    text = (raw or "").strip()
    for pattern, message, retryable in _COMPILED:
        if pattern.search(text):
            return Explained(message, retryable)
    # Taninmayan hatalar cogunlukla gecici oluyor; deneme sayisi zaten sinirli.
    return Explained(text or "Bilinmeyen hata.", True)
