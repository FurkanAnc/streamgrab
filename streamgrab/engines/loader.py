"""Motor tanimlarini (engines/*.json) yukler ve calistirilabilir komutu cozer.

Tasarim karari: extractor mantigi koda gomulmez. Her motor bir JSON dosyasidir;
uygulama sadece "argv oneki + arguman + satir kurallari" bilir. Boylece yeni bir
motor eklemek kod degil, veri degisikligidir.
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core.runner import run_capture
from ..core.tools import find_js_runtime
from ..paths import bin_dir, engines_dir, is_frozen, python_exe


@dataclass
class Engine:
    spec: dict[str, Any]
    argv: list[str]
    source: str  # "bundle" | "path" | "module"
    js_runtime: str = ""  # "deno:<yol>" veya "node:<yol>"; YouTube icin gerekli
    _version: str | None = field(default=None, repr=False)

    # ------------------------------------------------------------- temel
    @property
    def id(self) -> str:
        return self.spec["id"]

    @property
    def display_name(self) -> str:
        return self.spec.get("displayName", self.id)

    @property
    def progress_marker(self) -> str:
        return self.spec.get("progressMarker", "@@PROG@@")

    @property
    def requires_ffmpeg(self) -> bool:
        return bool(self.spec.get("requiresFfmpeg", False))

    # ---------------------------------------------------------- komutlar
    def command(self, *args: str) -> list[str]:
        """Temel argumanlar + verilen argumanlarla tam komut satirini kurar."""
        runtime: list[str] = []
        flag = self.spec.get("jsRuntimeArg")
        if flag and self.js_runtime:
            runtime = [flag, self.js_runtime]
        return [*self.argv, *self.spec.get("baseArgs", []), *runtime, *map(str, args)]

    def probe_command(self, url: str, cookies: str = "", single: bool = False) -> list[str]:
        """Metadata komutu; single=True listeyi yok sayip sadece videoya bakar."""
        mode = "probeSingleArgs" if single else "probePlaylistArgs"
        args = [*self.spec.get("probeArgs", []), *self.spec.get(mode, [])]
        if cookies:
            args += ["--cookies-from-browser", cookies]
        args.append(url)
        return self.command(*args)

    def speed_arguments(
        self,
        *,
        fragments: int = 1,
        aria2_exe: str = "",
        chunk_size: str = "",
        throttled_rate: bool = False,
    ) -> list[str]:
        """Hizi etkileyen argumanlar tek yerde toplanir.

        * --concurrent-fragments : HLS/DASH parcalarini paralel indirir (en buyuk kazanc)
        * --downloader aria2c    : duz http(s) dosyalarini Range ile parcalayarak indirir
        * --http-chunk-size      : tek baglantiyi Range isteklerine boler
        * --throttled-rate       : sunucu yavaslattiysa baglantiyi yeniler (YouTube)
        """
        args: list[str] = []
        if fragments and int(fragments) > 1:
            args += ["--concurrent-fragments", str(int(fragments))]
        if aria2_exe:
            args += ["--downloader", f"aria2c:{aria2_exe}"]
            args += [
                "--downloader-args",
                "aria2c:-x8 -s8 -k1M --file-allocation=none --console-log-level=warn "
                "--summary-interval=1",
            ]
        if chunk_size:
            args += ["--http-chunk-size", chunk_size]
        if throttled_rate:
            args += ["--throttled-rate", "100K"]
        return args

    def download_command(
        self,
        url: str,
        outdir: str,
        selector: str,
        *,
        cookies: str = "",
        ffmpeg_dir: str = "",
        audio_only: bool = False,
        merge_format: str = "mp4",
        write_subs: bool = False,
        embed_metadata: bool = True,
        fragments: int = 1,
        aria2_exe: str = "",
        chunk_size: str = "",
        throttled_rate: bool = False,
        archive_file: str = "",
        filename_prefix: str = "",
        format_sort: str = "",
    ) -> list[str]:
        spec = self.spec
        args: list[str] = [*spec.get("downloadArgs", [])]
        args += self.speed_arguments(
            fragments=fragments,
            aria2_exe=aria2_exe,
            chunk_size=chunk_size,
            throttled_rate=throttled_rate,
        )

        template = spec.get("progressTemplate")
        if template:
            args += ["--progress-template", template]

        args += ["-o", f"{filename_prefix}%(title).150B [%(id)s].%(ext)s", "-P", outdir]
        if archive_file:
            args += ["--download-archive", archive_file]

        if ffmpeg_dir:
            args += ["--ffmpeg-location", ffmpeg_dir]
        if cookies:
            args += ["--cookies-from-browser", cookies]
        if write_subs:
            args += ["--write-subs", "--write-auto-subs", "--embed-subs"]

        if format_sort:
            args += ["-S", format_sort]

        if audio_only:
            args += ["-f", selector, "-x", "--audio-format", "mp3", "--audio-quality", "0"]
        else:
            args += ["-f", selector]
            if merge_format:
                args += ["--merge-output-format", merge_format]

        if embed_metadata:
            args += ["--embed-metadata", "--embed-thumbnail"]

        args.append(url)
        return self.command(*args)

    # ---------------------------------------------------------- versiyon
    def version(self, refresh: bool = False) -> str:
        if self._version and not refresh:
            return self._version
        code, out = run_capture(self.command(*self.spec.get("versionArgs", ["--version"])), timeout=30)
        lines = [line.strip() for line in out.splitlines() if line.strip()]
        self._version = lines[0] if code == 0 and lines else "bilinmiyor"
        return self._version


# --------------------------------------------------------------- cozumleme
def _candidate_paths(entry: str) -> list[Path]:
    path = Path(entry)
    if path.is_absolute():
        return [path]
    # Once depo koku, sonra bin/ klasoru.
    return [Path(entry), bin_dir() / Path(entry).name]


def _resolve_executable(spec: dict[str, Any]) -> tuple[list[str], str] | None:
    exe_spec = spec.get("executable", {})
    keys = ["windows", "any"] if sys.platform == "win32" else ["any"]
    entries: list[str] = []
    for key in keys:
        entries.extend(exe_spec.get(key, []))

    for entry in entries:
        for candidate in _candidate_paths(entry):
            try:
                if candidate.is_file():
                    return [str(candidate)], "bundle"
            except OSError:
                continue

    for entry in entries:
        found = shutil.which(Path(entry).name)
        if found:
            return [found], "path"

    return None


def _module_available(module: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def load_engine(engine_id: str = "yt-dlp") -> Engine | None:
    path = engines_dir() / f"{engine_id}.json"
    if not path.is_file():
        return None

    with path.open("r", encoding="utf-8") as handle:
        spec = json.load(handle)

    resolved = _resolve_executable(spec)
    if resolved:
        argv, source = resolved
        return Engine(spec=spec, argv=argv, source=source, js_runtime=find_js_runtime())

    # Paketli exe'de sys.executable Python degil, uygulamanin kendisidir.
    fallback = None if is_frozen() else spec.get("moduleFallback")
    if fallback:
        module = fallback[-1].replace("-", "_")
        if _module_available(module):
            return Engine(
                spec=spec,
                argv=[python_exe(), *fallback],
                source="module",
                js_runtime=find_js_runtime(),
            )

    return Engine(spec=spec, argv=[spec["id"]], source="missing")


def available_engines() -> list[Engine]:
    engines: list[Engine] = []
    for path in sorted(engines_dir().glob("*.json")):
        engine = load_engine(path.stem)
        if engine:
            engines.append(engine)
    return engines
