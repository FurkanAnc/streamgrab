"""Testler gercek %APPDATA%\\StreamGrab ve Downloads klasorune dokunmaz."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_SANDBOX = tempfile.mkdtemp(prefix="streamgrab-test-")
os.environ["APPDATA"] = _SANDBOX
os.environ["USERPROFILE"] = _SANDBOX
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
