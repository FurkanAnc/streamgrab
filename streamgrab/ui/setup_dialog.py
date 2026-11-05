"""Ilk acilis kurulumu: eksik araclari tek tikla indirir."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..config import Config
from ..core.updater import DOWNLOADERS
from .chrome import apply_dark_titlebar

TOOL_TEXT = {
    "yt-dlp": "yt-dlp — videoları çözümler ve indirir (yaklaşık 20 MB)",
    "ffmpeg": "ffmpeg — ses ve görüntüyü birleştirir (yaklaşık 200 MB)",
    "deno": "deno — YouTube'un tüm formatlarını açar (yaklaşık 45 MB)",
}


class SetupThread(QThread):
    tool_started = Signal(str)
    progressed = Signal(int, int)
    failed = Signal(str)

    def __init__(self, tools: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tools = tools

    def run(self) -> None:  # pragma: no cover - ag islemi
        try:
            for tool in self._tools:
                self.tool_started.emit(tool)
                DOWNLOADERS[tool](lambda done, total: self.progressed.emit(done, total))
        except Exception as exc:  # noqa: BLE001 - kullaniciya gosterilir
            self.failed.emit(str(exc))


class SetupDialog(QDialog):
    def __init__(self, config: Config, missing: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.missing = missing
        self._thread: SetupThread | None = None
        self._failed = False

        self.setWindowTitle("Kurulum")
        self.setMinimumWidth(520)
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(12)

        heading = QLabel("StreamGrab'i hazırlayalım")
        heading.setObjectName("Title")
        root.addWidget(heading)

        intro = QLabel("İndirme yapabilmek için şu araçlar gerekiyor:")
        intro.setWordWrap(True)
        root.addWidget(intro)

        tools = QLabel("\n".join(f"•  {TOOL_TEXT[tool]}" for tool in missing))
        tools.setObjectName("Muted")
        tools.setWordWrap(True)
        root.addWidget(tools)

        self.status = QLabel("Resmi kaynaklardan indirilir ve doğrulanır.")
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        self.bar.setVisible(False)
        root.addWidget(self.bar)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.later_button = QPushButton("Sonra")
        self.later_button.clicked.connect(self._later)
        self.install_button = QPushButton("Kur")
        self.install_button.setObjectName("Primary")
        self.install_button.clicked.connect(self._install)
        buttons.addWidget(self.later_button)
        buttons.addWidget(self.install_button)
        root.addLayout(buttons)

    def _later(self) -> None:
        self.config.set("setup_dismissed", True)
        self.config.save()
        self.reject()

    def _install(self) -> None:
        self._failed = False
        self.install_button.setEnabled(False)
        self.later_button.setEnabled(False)
        self.bar.setVisible(True)
        self.bar.setValue(0)

        self._thread = SetupThread(self.missing, self)
        self._thread.tool_started.connect(self._on_tool_started)
        self._thread.progressed.connect(self._on_progress)
        self._thread.failed.connect(self._on_failed)
        self._thread.finished.connect(self._on_finished)
        self._thread.start()

    def _on_tool_started(self, tool: str) -> None:
        self.bar.setValue(0)
        self.status.setText(f"{tool} indiriliyor…")

    def _on_progress(self, done: int, total: int) -> None:
        if total > 0:
            self.bar.setValue(int(done / total * 1000))

    def _on_failed(self, message: str) -> None:
        self._failed = True
        QMessageBox.critical(self, "Kurulum başarısız", message)

    def _on_finished(self) -> None:
        if self._failed:
            self.status.setText("Kurulum tamamlanamadı. İnternet bağlantını kontrol edip tekrar dene.")
            self.install_button.setEnabled(True)
            self.later_button.setEnabled(True)
            self.bar.setVisible(False)
            return
        self.accept()

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
        apply_dark_titlebar(self)
        super().showEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._thread and self._thread.isRunning():
            event.ignore()  # yarim kalan indirme thread'i pencereyle yok edilemez
            return
        super().closeEvent(event)

    def reject(self) -> None:
        if self._thread and self._thread.isRunning():
            return
        super().reject()
