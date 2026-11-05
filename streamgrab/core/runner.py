"""Alt surec yardimcilari.

Windows'a ozgu iki detay onemli:
  * CREATE_NO_WINDOW  -> indirme sirasinda siyah konsol penceresi acilmaz
  * taskkill /T       -> iptal edince yt-dlp'nin cagirdigi ffmpeg cocugu da olur
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Iterable

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _startup_kwargs() -> dict:
    if os.name == "nt":
        info = subprocess.STARTUPINFO()
        info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return {"startupinfo": info, "creationflags": CREATE_NO_WINDOW}
    return {}


def _child_env() -> dict | None:
    """Paketli uygulama alt sureclere PyInstaller ortamini sizdirmesin.

    yt-dlp.exe de PyInstaller ile paketli; bu degisken olmadan kendini bizim
    surecimizin bir parcasi sanabilir.
    """
    if not getattr(sys, "frozen", False):
        return None
    env = dict(os.environ)
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def hidden_popen(argv: Iterable[str], cwd: str | None = None) -> subprocess.Popen:
    """Ciktisi satir satir okunacak bir alt surec baslatir."""
    return subprocess.Popen(
        list(argv),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        cwd=cwd,
        env=_child_env(),
        **_startup_kwargs(),
    )


def run_capture(argv: Iterable[str], timeout: float = 60) -> tuple[int, str]:
    """Kisa komutlar (--version, -J) icin bloklayan calistirma."""
    try:
        completed = subprocess.run(
            list(argv),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=_child_env(),
            **_startup_kwargs(),
        )
        return completed.returncode, completed.stdout or ""
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or ""
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")
        return -1, out
    except OSError as exc:
        return -1, f"{exc}"


def kill_tree(process: subprocess.Popen | None) -> None:
    """Sureci ve tum cocuklarini sonlandirir."""
    if process is None or process.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **_startup_kwargs(),
            )
        else:
            process.terminate()
    except OSError:
        pass
    finally:
        try:
            process.wait(timeout=5)
        except (subprocess.TimeoutExpired, OSError):
            try:
                process.kill()
            except OSError:
                pass


def python_has_module(module: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def default_python() -> str:
    return sys.executable
