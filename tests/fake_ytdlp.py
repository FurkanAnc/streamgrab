"""Gercek ag olmadan yt-dlp davranisini taklit eden sahte motor.

Davranis URL ile secilir:
    fake://ok       ilerleme basar, 0 ile cikar
    fake://slow     yavas ilerler (durdurma testleri icin)
    fake://flaky    ilk calismada ag hatasi, sonra basarili (--state dosyasi)
    fake://private  kalici hata
    fake://archive  arsivde kayitli gibi atlar
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

url = sys.argv[-1]
state = Path(sys.argv[1])
state.parent.mkdir(parents=True, exist_ok=True)
with state.open("a", encoding="utf-8") as handle:
    handle.write(url + "\n")
runs = state.read_text(encoding="utf-8").splitlines().count(url)


def progress(done: int) -> None:
    print(f"@@PROG@@{done};100;NA;10;1", flush=True)


if url == "fake://ok":
    print("[download] Destination: C:\\out\\ok.mp4", flush=True)
    progress(100)
elif url == "fake://slow":
    for step in range(600):
        progress(step % 100)
        time.sleep(0.05)
elif url == "fake://flaky":
    if runs == 1:
        print("ERROR: unable to download video data: <urlopen error timed out>", flush=True)
        raise SystemExit(1)
    print("[download] Destination: C:\\out\\flaky.mp4", flush=True)
    progress(100)
elif url == "fake://private":
    print("ERROR: [youtube] abc: Private video. Sign in if you've been granted access", flush=True)
    raise SystemExit(1)
elif url == "fake://archive":
    print("[download] abc: Bir video has already been recorded in the archive", flush=True)
