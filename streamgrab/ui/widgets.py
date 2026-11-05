"""Paylasilan parcalar: kuyruk satiri, bos durum, kisaltilan etiket."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..core.downloader import Job
from ..core.errors import explain
from . import theme
from .chrome import ICON_SIZE, icon, icon_pixmap
from .format import human_eta, human_size, human_speed

STATUS_TEXT = {
    "queued": "Sırada",
    "downloading": "İndiriliyor",
    "merging": "Birleştiriliyor",
    "paused": "Duraklatıldı",
    "waiting": "Yeniden denenecek",
    "done": "Tamamlandı",
    "failed": "Hata",
    "canceled": "İptal edildi",
}

STATUS_TONE = {
    "queued": "",
    "downloading": "active",
    "merging": "active",
    "paused": "warn",
    "waiting": "warn",
    "done": "ok",
    "failed": "bad",
    "canceled": "",
}


def _set_tone(widget: QWidget, tone: str) -> None:
    """QSS [tone=...] seciciligi ancak yeniden cilalaninca devreye girer."""
    if widget.property("tone") != tone:
        widget.setProperty("tone", tone)
        widget.style().unpolish(widget)
        widget.style().polish(widget)


class EmptyState(QWidget):
    """Sayfa bosken gosterilen ikon + baslik + aciklama."""

    def __init__(self, icon_name: str, title: str, text: str, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.addStretch(1)

        image = QLabel()
        image.setPixmap(icon_pixmap(icon_name, theme.TEXT_FAINT, 44, 1.5))
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading = QLabel(title)
        heading.setObjectName("EmptyTitle")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body = QLabel(text)
        body.setObjectName("EmptyText")
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(image)
        layout.addSpacing(6)
        layout.addWidget(heading)
        layout.addWidget(body)
        layout.addStretch(1)


class ElidedLabel(QLabel):
    """Uzun metni satiri tasirmadan '...' ile kisaltir (min genislik = 0)."""

    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(text, parent)
        self._full_text = text
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)

    def setText(self, text: str) -> None:  # noqa: N802 - Qt API
        self._full_text = text or ""
        self._apply_elide()

    def fullText(self) -> str:
        return self._full_text

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._apply_elide()

    def _apply_elide(self) -> None:
        width = max(24, self.width() - 2)
        if width <= 24 and not self._full_text:  # henuz yerlesmedi
            QLabel.setText(self, self._full_text)
            return
        QLabel.setText(
            self, self.fontMetrics().elidedText(self._full_text, Qt.TextElideMode.ElideRight, width)
        )


class JobRow(QFrame):
    cancel_requested = Signal(str)
    open_requested = Signal(str)
    pause_requested = Signal(str)
    resume_requested = Signal(str)

    def __init__(self, job: Job, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Job")
        self.job_id = job.id

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(7)

        top = QHBoxLayout()
        top.setSpacing(10)
        self.title = ElidedLabel("")
        self.title.setObjectName("H1")
        self.status = QLabel("")
        self.status.setObjectName("Pill")
        top.addWidget(self.title, 1)
        top.addWidget(self.status, 0)
        layout.addLayout(top)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)

        bottom = QHBoxLayout()
        bottom.setSpacing(2)
        self.detail = ElidedLabel("")
        self.detail.setObjectName("Muted")
        bottom.addWidget(self.detail, 1)

        self.open_button = self._icon_button("folder", "Klasörde göster")
        self.open_button.clicked.connect(lambda: self.open_requested.emit(self.job_id))
        bottom.addWidget(self.open_button)

        self.pause_button = self._icon_button("pause", "Duraklat")
        self.pause_button.clicked.connect(lambda: self.pause_requested.emit(self.job_id))
        bottom.addWidget(self.pause_button)

        self.resume_button = self._icon_button("play", "Devam et")
        self.resume_button.clicked.connect(lambda: self.resume_requested.emit(self.job_id))
        bottom.addWidget(self.resume_button)

        self.cancel_button = self._icon_button("x", "İptal")
        self.cancel_button.clicked.connect(lambda: self.cancel_requested.emit(self.job_id))
        bottom.addWidget(self.cancel_button)

        layout.addLayout(bottom)
        self.refresh(job)

    def _icon_button(self, name: str, tooltip: str) -> QPushButton:
        button = QPushButton()
        button.setObjectName("Icon")
        button.setIcon(icon(name))
        button.setIconSize(ICON_SIZE)
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def refresh(self, job: Job) -> None:
        self.title.setText(job.title or job.url)
        tooltip = f"{job.title}\n{job.url}"
        self.title.setToolTip(f"{job.playlist}\n{tooltip}" if job.playlist else tooltip)

        status = STATUS_TEXT.get(job.status, job.status)
        if job.status == "downloading" and job.total > 0:
            status = f"%{job.percent:.0f} · {status}"
        if job.status == "done" and job.skipped:
            status = "Atlandı"
        self.status.setText(status)
        tone = STATUS_TONE.get(job.status, "")
        _set_tone(self.status, tone)
        _set_tone(self.progress, tone)

        self.progress.setValue(int(job.percent * 10))

        parts: list[str] = []
        tooltip = ""
        if job.status == "downloading":
            if job.downloaded:
                parts.append(f"{human_size(job.downloaded)} / {human_size(job.total) if job.total else '?'}")
            if job.speed:
                parts.append(human_speed(job.speed))
            if job.eta:
                parts.append(f"{human_eta(job.eta)} kaldı")
        elif job.status == "failed":
            parts.append(explain(job.error).message)
            tooltip = job.error
        elif job.status == "waiting":
            parts.append(explain(job.error).message)
            parts.append(f"{job.attempts}. deneme birazdan başlayacak")
            tooltip = job.error
        elif job.status == "paused":
            if job.downloaded:
                parts.append(f"{human_size(job.downloaded)} / {human_size(job.total) if job.total else '?'}")
            parts.append("kaldığı yerden devam edecek")
        elif job.status == "done" and job.skipped:
            parts.append("Daha önce indirildiği için atlandı")
        elif job.status == "done":
            parts.append(job.filepath or "tamamlandı")
        elif job.status == "merging":
            parts.append("ffmpeg ses/video birleştiriyor…")
        elif job.status == "queued":
            parts.append("sırada bekliyor")

        self.detail.setText("  ·  ".join(p for p in parts if p))
        self.detail.setToolTip(tooltip or self.detail.fullText())

        self.pause_button.setVisible(job.status in ("queued", "downloading", "waiting"))
        self.resume_button.setVisible(job.status in ("paused", "failed", "canceled"))
        paused = job.status == "paused"
        self.resume_button.setIcon(icon("play" if paused else "retry"))
        self.resume_button.setToolTip("Devam et" if paused else "Tekrar dene")
        self.cancel_button.setVisible(
            job.status in ("queued", "downloading", "merging", "paused", "waiting")
        )
        self.open_button.setVisible(job.status == "done" and bool(job.filepath))
