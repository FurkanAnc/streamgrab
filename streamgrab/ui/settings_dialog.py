"""Ayarlar penceresi + motor guncelleme."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QFrame,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..config import Config
from ..core.tools import aria2_version, ffmpeg_version, find_aria2, find_js_runtime
from ..core.updater import DOWNLOADERS
from ..engines.loader import Engine
from .chrome import apply_dark_titlebar

BROWSERS = [
    ("(kullanma)", ""),
    ("Chrome", "chrome"),
    ("Edge", "edge"),
    ("Firefox", "firefox"),
    ("Brave", "brave"),
    ("Opera", "opera"),
    ("Vivaldi", "vivaldi"),
    ("Chromium", "chromium"),
]

DOWNLOADERS = [
    ("Otomatik (varsa aria2c)", "auto"),
    ("yt-dlp yerleşik indirici", "native"),
    ("aria2c (zorunlu)", "aria2"),
]

CHUNK_SIZES = ["", "1M", "5M", "10M", "25M", "50M"]

SOURCE_TEXT = {
    "bundle": "uygulama ile birlikte",
    "path": "sistem PATH",
    "module": "python -m yt_dlp",
    "missing": "bulunamadı",
}


class UpdateThread(QThread):
    progressed = Signal(int, int)
    succeeded = Signal(str, str)  # (kind, yol)
    failed = Signal(str)

    def __init__(self, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kind = kind

    def run(self) -> None:  # pragma: no cover - ag islemi
        try:
            callback = lambda done, total: self.progressed.emit(done, total)  # noqa: E731
            path = DOWNLOADERS[self.kind](callback)
            self.succeeded.emit(self.kind, str(path))
        except Exception as exc:  # noqa: BLE001 - kullaniciya gosterilecek
            self.failed.emit(str(exc))


class SettingsDialog(QDialog):
    def __init__(
        self,
        config: Config,
        engine: Engine,
        ffmpeg_version: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.engine = engine
        self.ffmpeg_version = ffmpeg_version
        self.aria2_exe = find_aria2(str(config.get("aria2_path") or ""))
        self._thread: UpdateThread | None = None

        self.setWindowTitle("Ayarlar")
        self.setMinimumWidth(660)
        self.setModal(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 18)
        outer.setSpacing(12)

        # Kucuk ekranlarda da sigsin diye icerik kayar; butonlar sabit kalir.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("Root")
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        root = QVBoxLayout(body)
        root.setContentsMargins(22, 20, 22, 4)
        root.setSpacing(14)

        heading = QLabel("Ayarlar")
        heading.setObjectName("Title")
        root.addWidget(heading)

        # ---------------------------------------------------------- indirme
        root.addWidget(self._section("İndirme"))

        download_form = QFormLayout()
        download_form.setSpacing(12)
        download_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        folder_row = QHBoxLayout()
        folder_row.setContentsMargins(0, 0, 0, 0)
        self.folder_edit = QLineEdit(str(config.get("download_dir")))
        browse = QPushButton("Gözat")
        browse.clicked.connect(self._pick_folder)
        folder_row.addWidget(self.folder_edit, 1)
        folder_row.addWidget(browse)
        folder_widget = QWidget()
        folder_widget.setLayout(folder_row)
        download_form.addRow("İndirme klasörü", folder_widget)

        self.concurrent = QSpinBox()
        self.concurrent.setRange(1, 8)
        self.concurrent.setValue(int(config.get("max_concurrent", 4)))
        self.concurrent.setSuffix(" paralel")
        download_form.addRow("Eş zamanlı indirme", self.concurrent)

        self.cookies = QComboBox()
        for label, value in BROWSERS:
            self.cookies.addItem(label, value)
        self.cookies.setCurrentIndex(max(0, self.cookies.findData(str(config.get("cookies_browser") or ""))))
        download_form.addRow("Tarayıcı çerezleri", self.cookies)

        self.retries = QSpinBox()
        self.retries.setRange(0, 10)
        self.retries.setValue(int(config.get("auto_retry", 3)))
        self.retries.setSuffix(" deneme")
        self.retries.setToolTip("Bağlantı sorunlarında otomatik yeniden deneme sayısı. 0 = kapalı.")
        download_form.addRow("Otomatik tekrar", self.retries)

        self.use_archive = QCheckBox("Daha önce indirilen videoları atla")
        self.use_archive.setChecked(bool(config.get("use_archive", True)))
        download_form.addRow("", self.use_archive)

        self.resume_on_start = QCheckBox("Yarım kalan indirmelere açılışta devam et")
        self.resume_on_start.setChecked(bool(config.get("resume_on_start", True)))
        download_form.addRow("", self.resume_on_start)

        self.playlist_subfolder = QCheckBox("Oynatma listelerini ayrı klasöre indir")
        self.playlist_subfolder.setChecked(bool(config.get("playlist_subfolder", True)))
        download_form.addRow("", self.playlist_subfolder)
        root.addLayout(download_form)

        # -------------------------------------------------------------- hiz
        root.addWidget(self._section("Hız"))

        speed_form = QFormLayout()
        speed_form.setSpacing(12)
        speed_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.fragments = QSpinBox()
        self.fragments.setRange(1, 16)
        self.fragments.setValue(int(config.get("concurrent_fragments", 8)))
        self.fragments.setSuffix(" parça")
        self.fragments.setToolTip(
            "HLS/DASH videoları parça parça iner. 8 parça genelde 3–5 kat hız demek.\n"
            "16 üstü çoğu sunucuda 403/rate-limit riski taşır."
        )
        speed_form.addRow("Paralel parça", self.fragments)

        self.downloader = QComboBox()
        for label, value in DOWNLOADERS:
            self.downloader.addItem(label, value)
        self.downloader.setCurrentIndex(
            max(0, self.downloader.findData(str(config.get("external_downloader") or "auto")))
        )
        self.downloader.setToolTip(
            "aria2c, düz mp4 gibi tek dosyaları HTTP Range ile 8 parçaya bölüp paralel çeker."
        )
        speed_form.addRow("Harici indirici", self.downloader)

        self.chunk = QComboBox()
        self.chunk.setEditable(True)
        for size in CHUNK_SIZES:
            self.chunk.addItem(size or "kapalı", size)
        current_chunk = str(config.get("http_chunk_size") or "")
        self.chunk.setCurrentText(current_chunk or "kapalı")
        self.chunk.setToolTip("Tek bağlantıyı Range isteklerine böler. Boş = kapalı.")
        speed_form.addRow("HTTP chunk boyutu", self.chunk)

        self.throttle = QCheckBox("Sunucu yavaşlatırsa bağlantıyı yenile (--throttled-rate)")
        self.throttle.setChecked(bool(config.get("throttled_rate", True)))
        speed_form.addRow("", self.throttle)
        root.addLayout(speed_form)

        # ----------------------------------------------------------- araclar
        root.addWidget(self._section("Araçlar"))

        tools_form = QFormLayout()
        tools_form.setSpacing(12)
        tools_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.ffmpeg_edit = QLineEdit(str(config.get("ffmpeg_path")))
        self.ffmpeg_edit.setPlaceholderText("otomatik (PATH / bin klasörü)")
        tools_form.addRow("ffmpeg yolu", self.ffmpeg_edit)

        self.aria2_edit = QLineEdit(str(config.get("aria2_path")))
        self.aria2_edit.setPlaceholderText("otomatik (bin/aria2c.exe / PATH)")
        tools_form.addRow("aria2c yolu", self.aria2_edit)

        self.engine_label = QLabel()
        self.engine_label.setObjectName("Muted")
        tools_form.addRow("", self.engine_label)

        root.addLayout(tools_form)

        update_row = QHBoxLayout()
        self.update_button = QPushButton("yt-dlp'yi güncelle")
        self.update_button.clicked.connect(lambda: self._start_update("yt-dlp"))
        self.ffmpeg_button = QPushButton("ffmpeg indir")
        self.ffmpeg_button.clicked.connect(lambda: self._start_update("ffmpeg"))
        self.deno_button = QPushButton("deno indir")
        self.deno_button.setToolTip("YouTube'un tüm formatları için gereken JavaScript ortamı.")
        self.deno_button.clicked.connect(lambda: self._start_update("deno"))
        self.aria2_button = QPushButton("aria2c indir")
        self.aria2_button.clicked.connect(lambda: self._start_update("aria2"))
        self._tool_buttons = (
            self.update_button,
            self.ffmpeg_button,
            self.deno_button,
            self.aria2_button,
        )
        for button in self._tool_buttons:
            update_row.addWidget(button)
        update_row.addStretch(1)
        root.addLayout(update_row)

        self.update_bar = QProgressBar()
        self.update_bar.setRange(0, 1000)
        self.update_bar.setTextVisible(False)
        self.update_bar.setVisible(False)
        root.addWidget(self.update_bar)

        root.addStretch(1)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(22, 0, 22, 0)
        buttons.addStretch(1)
        cancel = QPushButton("Vazgeç")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Kaydet")
        save.setObjectName("Primary")
        save.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        outer.addLayout(buttons)

        available = self.screen().availableGeometry().height()
        self.resize(self.minimumWidth(), min(body.sizeHint().height() + 80, available - 80))

        self._refresh_tool_labels()

    # ------------------------------------------------------------ yardimci
    def _section(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("Section")
        return label

    def _refresh_tool_labels(self) -> None:
        source = SOURCE_TEXT.get(self.engine.source, self.engine.source)
        ffmpeg_text = f"ffmpeg {self.ffmpeg_version}" if self.ffmpeg_version else "ffmpeg bulunamadı"
        runtime = find_js_runtime().split(":", 1)[0]
        self.ffmpeg_button.setText("ffmpeg'i güncelle" if self.ffmpeg_version else "ffmpeg indir")
        self.deno_button.setText("deno'yu güncelle" if runtime == "deno" else "deno indir")
        self.engine_label.setText(
            f"{self.engine.display_name} {self.engine.version()}  ·  kaynak: {source}  ·  "
            f"{ffmpeg_text}  ·  JS: {runtime or 'yok'}"
        )

        self.aria2_exe = find_aria2(self.aria2_edit.text().strip())
        if self.aria2_exe:
            version = aria2_version(self.aria2_exe)
            self.aria2_button.setText("aria2c'yi güncelle")
            self.aria2_edit.setToolTip(self.aria2_exe)
            self.engine_label.setText(self.engine_label.text() + f"  ·  aria2 {version or '?'}")
        else:
            self.aria2_button.setText("aria2c indir")
            self.aria2_edit.setToolTip("")

    def _pick_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "İndirme klasörü", self.folder_edit.text())
        if folder:
            self.folder_edit.setText(folder)

    def _save(self) -> None:
        chunk = self.chunk.currentData()
        if chunk is None:
            text = self.chunk.currentText().strip()
            chunk = "" if text in ("", "kapalı") else text

        self.config.update(
            {
                "download_dir": self.folder_edit.text().strip() or str(Path.home() / "Downloads"),
                "max_concurrent": self.concurrent.value(),
                "cookies_browser": self.cookies.currentData(),
                "auto_retry": self.retries.value(),
                "use_archive": self.use_archive.isChecked(),
                "resume_on_start": self.resume_on_start.isChecked(),
                "playlist_subfolder": self.playlist_subfolder.isChecked(),
                "ffmpeg_path": self.ffmpeg_edit.text().strip(),
                "aria2_path": self.aria2_edit.text().strip(),
                "concurrent_fragments": self.fragments.value(),
                "external_downloader": self.downloader.currentData(),
                "http_chunk_size": chunk,
                "throttled_rate": self.throttle.isChecked(),
            }
        )
        self.config.save()
        self.accept()

    # ---------------------------------------------------------- guncelleme
    def _start_update(self, kind: str) -> None:
        for button in self._tool_buttons:
            button.setEnabled(False)
        self.update_bar.setVisible(True)
        self.update_bar.setValue(0)

        self._thread = UpdateThread(kind, self)
        self._thread.progressed.connect(self._on_progress)
        self._thread.succeeded.connect(self._on_updated)
        self._thread.failed.connect(self._on_update_failed)
        self._thread.start()

    def _on_progress(self, done: int, total: int) -> None:
        if total > 0:
            self.update_bar.setValue(int(done / total * 1000))

    def _on_updated(self, kind: str, path: str) -> None:
        for button in self._tool_buttons:
            button.setEnabled(True)
        self.update_bar.setVisible(False)
        if kind == "aria2":
            self.aria2_edit.setText(path)
        if kind == "ffmpeg":
            self.ffmpeg_version = ffmpeg_version(self.ffmpeg_edit.text().strip())
        self.engine.version(refresh=True)
        self._refresh_tool_labels()
        QMessageBox.information(self, "Hazır", f"{kind} kuruldu:\n{path}")

    def _on_update_failed(self, message: str) -> None:
        for button in self._tool_buttons:
            button.setEnabled(True)
        self.update_bar.setVisible(False)
        QMessageBox.critical(self, "Güncelleme başarısız", message)

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
        apply_dark_titlebar(self)
        super().showEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._thread and self._thread.isRunning():
            self._thread.wait(3000)
        super().closeEvent(event)
