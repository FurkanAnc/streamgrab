"""README icin onizleme gorseli uretir (indirme baslatmaz).

Kullanim:  .venv\\Scripts\\python.exe tools\\screenshot.py [url]
Cikti:     docs/preview.png
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from streamgrab.config import Config  # noqa: E402
from streamgrab.core.downloader import Job  # noqa: E402
from streamgrab.core.probe import probe  # noqa: E402
from streamgrab.engines.loader import load_engine  # noqa: E402
from streamgrab.ui.main_window import MainWindow  # noqa: E402
from streamgrab.ui.theme import STYLE  # noqa: E402
from streamgrab.ui.widgets import JobRow  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/watch?v=aqz-KE-bpKQ"


def main() -> int:
    engine = load_engine()
    info = probe(engine, URL)

    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(STYLE)

    window = MainWindow(Config.load())
    window.resize(1120, 860)
    window.move(-4000, -4000)  # kullaniciyi rahatsiz etmemek icin ekran disi
    window.show()
    window._on_probe_done(info)  # noqa: SLF001 - demo verisi

    running = Job(url=info.url, title=info.title, selector="bv*+ba/b", outdir="C:/Downloads")
    running.status = "downloading"
    running.downloaded, running.total = 182e6, 421e6
    running.speed, running.eta = 8.4e6, 28
    window.queue_layout.insertWidget(0, JobRow(running, window))

    done = Job(
        url="https://youtu.be/xyz",
        title="Başka bir video — tamamlanmış örnek",
        selector="b",
        outdir="C:/Downloads",
    )
    done.status = "done"
    done.total = done.downloaded = 9.4e6
    done.filepath = r"C:\Users\asusl\Downloads\StreamGrab\ornek-video [xyz].mp4"
    window.queue_layout.insertWidget(1, JobRow(done, window))

    window.empty_label.setVisible(False)
    window.queue_count.setText("2 iş · 1 aktif")

    def capture() -> None:
        target = ROOT / "docs" / "preview.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        window.grab().save(str(target))
        print(f"yazildi: {target}")
        window.close()
        app.quit()

    QTimer.singleShot(2500, capture)  # kucuk resmin (thumbnail) yuklenmesini bekle
    code = app.exec()
    window.deleteLater()
    app.processEvents()
    del window
    return code


if __name__ == "__main__":
    raise SystemExit(main())
