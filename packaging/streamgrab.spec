# PyInstaller tanimi: tek klasorlu (--onedir), konsolsuz paket.
#
# yt-dlp / ffmpeg / deno pakete girmez: ilk acilista indirilir ve uygulamadan
# bagimsiz guncellenir. Boylece kurulum dosyasi kucuk kalir.

from pathlib import Path

ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT)],
    datas=[
        (str(ROOT / "streamgrab" / "engines" / "*.json"), "streamgrab/engines"),
        (str(ROOT / "streamgrab" / "assets" / "*.*"), "streamgrab/assets"),
    ],
    excludes=["yt_dlp", "yt_dlp_ejs", "tkinter", "unittest", "pytest"],
)

# Qt'nin OpenSSL eklentisi, Python'un paketledigi OpenSSL ile cakisip ilk HTTPS
# isteginde cokuyor (0xC0000005). Eklenti olmayinca Qt, Windows'un Schannel
# katmanini kullanir.
a.binaries = [item for item in a.binaries if "qopensslbackend" not in item[0].lower()]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="StreamGrab",
    console=False,
    upx=False,
    icon=str(ROOT / "streamgrab" / "assets" / "icon.ico"),
)

coll = COLLECT(exe, a.binaries, a.datas, name="StreamGrab", upx=False)
