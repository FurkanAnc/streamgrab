"""StreamGrab giris noktasi."""

from __future__ import annotations

import faulthandler
import sys
import traceback

from PySide6.QtCore import QLockFile
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from .config import Config
from .paths import APP_NAME, assets_dir, lock_file, log_file
from .ui.main_window import MainWindow
from .ui.theme import STYLE


def _install_excepthook() -> None:
    def hook(exc_type, exc_value, exc_tb) -> None:
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        if sys.stderr is not None:  # konsolsuz exe'de stderr yoktur
            sys.stderr.write(text)
        app = QApplication.instance()
        if app is not None:
            QMessageBox.critical(None, "Beklenmeyen hata", text[-2000:])

    sys.excepthook = hook


def main() -> int:
    # Konsolsuz exe'de yerel cokmeler (access violation) baska turlu iz birakmaz.
    crash_log = log_file().open("a", encoding="utf-8")
    faulthandler.enable(crash_log, all_threads=True)

    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("streamgrab.app.1")
        except Exception:  # noqa: BLE001 - kozmetik
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setStyle("Fusion")
    font = QFont()
    font.setFamilies(["Segoe UI Variable Text", "Segoe UI"])
    font.setPointSize(10)
    app.setFont(font)
    app.setStyleSheet(STYLE)
    icon = assets_dir() / "icon.ico"
    if icon.is_file():
        app.setWindowIcon(QIcon(str(icon)))
    _install_excepthook()

    # Iki kopya ayni kuyrugu ayni anda devam ettirip dosyalari bozmasin.
    lock = QLockFile(str(lock_file()))
    if not lock.tryLock(0):
        QMessageBox.information(None, APP_NAME, "StreamGrab zaten açık.")
        return 0

    config = Config.load()
    window = MainWindow(config)
    window.show()
    urls = [arg for arg in sys.argv[1:] if arg.lower().startswith(("http://", "https://"))]
    if urls:
        window.analyze_url(urls[0])
    code = app.exec()

    # Qt nesneleri QApplication'dan once yikilmalidir; aksi halde cikista
    # nadiren heap corruption (0xC0000374 / access violation) gorulebiliyor.
    window.deleteLater()
    app.processEvents()
    del window
    return code


if __name__ == "__main__":
    raise SystemExit(main())
