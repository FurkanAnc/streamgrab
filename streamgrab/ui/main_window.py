"""Ana pencere: URL -> analiz -> format secimi -> kuyruk."""

from __future__ import annotations

import os
import subprocess
import sys

from PySide6.QtCore import QThread, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..config import Config
from ..core import store
from ..core.downloader import DownloadManager, Job
from ..core.errors import explain
from ..core.playlist import safe_folder_name
from ..core.probe import FormatInfo, MediaInfo, probe
from ..core.tools import find_aria2, find_ffmpeg, find_js_runtime, ffmpeg_version, missing_tools
from ..engines.loader import Engine, load_engine
from ..paths import archive_file
from . import theme
from .chrome import ICON_SIZE, apply_dark_titlebar, icon, icon_pixmap, rounded_thumbnail
from .format import human_duration, human_size
from .history_dialog import HistoryDialog
from .playlist_panel import PlaylistPanel
from .settings_dialog import SettingsDialog
from .setup_dialog import SetupDialog
from .widgets import EmptyState, JobRow

PRESETS: list[tuple[str, str, bool]] = [
    ("Otomatik — en iyi kalite", "bv*+ba/b", False),
    ("1080p'ye kadar", "bv*[height<=1080]+ba/b[height<=1080]", False),
    ("720p'ye kadar", "bv*[height<=720]+ba/b[height<=720]", False),
    ("Sadece ses (MP3)", "ba/b", True),
    ("Tablodan seç", "", False),
]
TABLE_PRESET_INDEX = len(PRESETS) - 1

# Secici ayni kalsa da yt-dlp varsayilan olarak bit hizina degil codec'e bakar.
PRESET_SORT = {PRESETS[1][1]: "res:1080,tbr"}

PAGE_NEW = 0
PAGE_QUEUE = 1

FILTERS: list[tuple[str, tuple[str, ...]]] = [
    ("Tümü", ()),
    ("Etkin", ("queued", "downloading", "merging", "waiting", "paused")),
    ("Tamamlanan", ("done",)),
    ("Sorunlu", ("failed", "canceled")),
]


class ProbeThread(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, engine: Engine, url: str, cookies: str, single: bool, parent=None) -> None:
        super().__init__(parent)
        self._engine = engine
        self._url = url
        self._cookies = cookies
        self._single = single

    def run(self) -> None:
        try:
            self.done.emit(probe(self._engine, self._url, self._cookies, single=self._single))
        except Exception as exc:  # noqa: BLE001 - kullaniciya gosterilir
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config
        self.engine: Engine = load_engine(str(config.get("engine")))  # type: ignore[assignment]
        self.ffmpeg_dir = find_ffmpeg(str(config.get("ffmpeg_path") or ""))
        self.ffmpeg_ver = ""
        self.aria2_exe = find_aria2(str(config.get("aria2_path") or ""))
        self.info: MediaInfo | None = None
        self._row_formats: dict[int, FormatInfo] = {}
        self._job_rows: dict[str, JobRow] = {}
        self._probe_thread: ProbeThread | None = None
        self._thumb_reply: QNetworkReply | None = None
        self._thumb_manager = QNetworkAccessManager(self)
        self._syncing_preset = False
        self._source_url = ""
        self._env_messages: list[str] = []

        self.manager = DownloadManager(config, self.engine, self)
        self.manager.changed.connect(self._on_job_changed)

        self.setWindowTitle("StreamGrab — video indirici")
        self.resize(1180, 800)
        self.setMinimumSize(960, 640)
        self.setAcceptDrops(True)

        self._build_ui()
        self._refresh_engine_status()
        self._validate_environment()
        self._restore_queue()
        QTimer.singleShot(0, self._offer_setup)

    # ------------------------------------------------------------- arayuz
    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)

        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_sidebar())

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_new_page())
        self.pages.addWidget(self._build_queue_page())
        outer.addWidget(self.pages, 1)

        self.statusBar().showMessage("Hazır")
        self.statusBar().setSizeGripEnabled(False)
        self._set_info_visible(False)
        self._show_page(PAGE_NEW)

    def _nav_button(self, text: str, icon_name: str, checkable: bool = True) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("Nav")
        button.setIcon(icon(icon_name, theme.TEXT_MUTED, theme.ACCENT_HOVER))
        button.setIconSize(ICON_SIZE)
        button.setCheckable(checkable)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def _build_sidebar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("Sidebar")
        bar.setFixedWidth(216)
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(12, 18, 12, 14)
        layout.setSpacing(4)

        brand = QHBoxLayout()
        brand.setContentsMargins(8, 0, 0, 14)
        brand.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(icon_pixmap("download", theme.ACCENT_HOVER, 22, 2.4))
        name = QLabel("StreamGrab")
        name.setObjectName("Brand")
        brand.addWidget(logo)
        brand.addWidget(name)
        brand.addStretch(1)
        layout.addLayout(brand)

        self.nav_new = self._nav_button("Yeni indirme", "plus")
        self.nav_new.clicked.connect(lambda: self._show_page(PAGE_NEW))
        layout.addWidget(self.nav_new)

        self.nav_queue = self._nav_button("İndirmeler", "list")
        self.nav_queue.clicked.connect(lambda: self._show_page(PAGE_QUEUE))
        badge_row = QHBoxLayout(self.nav_queue)
        badge_row.setContentsMargins(0, 0, 10, 0)
        badge_row.addStretch(1)
        self.queue_badge = QLabel("")
        self.queue_badge.setObjectName("Badge")
        self.queue_badge.setFixedHeight(18)
        self.queue_badge.setVisible(False)
        badge_row.addWidget(self.queue_badge, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.nav_queue)

        history = self._nav_button("Geçmiş", "clock", checkable=False)
        history.clicked.connect(self._open_history)
        layout.addWidget(history)

        layout.addStretch(1)

        settings = self._nav_button("Ayarlar", "settings", checkable=False)
        settings.clicked.connect(self._open_settings)
        layout.addWidget(settings)

        self.engine_chip = QLabel("motor aranıyor…")
        self.engine_chip.setObjectName("Chip")
        layout.addSpacing(6)
        layout.addWidget(self.engine_chip)
        return bar

    def _show_page(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        self.nav_new.setChecked(index == PAGE_NEW)
        self.nav_queue.setChecked(index == PAGE_QUEUE)

    def _page(self) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        page.setObjectName("Root")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 26, 32, 18)
        layout.setSpacing(14)
        return page, layout

    def _build_new_page(self) -> QWidget:
        page, layout = self._page()

        head = QVBoxLayout()
        head.setSpacing(2)
        title = QLabel("Yeni indirme")
        title.setObjectName("Title")
        subtitle = QLabel("Bağlantıyı yapıştır, kaliteyi seç, gerisi StreamGrab'de.")
        subtitle.setObjectName("Subtitle")
        head.addWidget(title)
        head.addWidget(subtitle)
        layout.addLayout(head)

        layout.addWidget(self._build_banner())
        layout.addWidget(self._build_url_card())

        self.busy_bar = QProgressBar()
        self.busy_bar.setObjectName("Busy")
        self.busy_bar.setRange(0, 0)
        self.busy_bar.setTextVisible(False)
        self.busy_bar.setVisible(False)
        layout.addWidget(self.busy_bar)

        self.info_card = self._build_info_card()
        layout.addWidget(self.info_card)
        layout.addWidget(self._build_formats_section(), 1)

        self.welcome = EmptyState(
            "link",
            "Başlamak için bir bağlantı yapıştır",
            "Tek video, oynatma listesi veya kanal bağlantısı olabilir.",
        )
        layout.addWidget(self.welcome, 1)
        return page

    def _build_banner(self) -> QWidget:
        self.banner = QLabel("")
        self.banner.setObjectName("Error")
        self.banner.setWordWrap(True)
        self.banner.setVisible(False)
        return self.banner

    def _build_url_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Hero")
        row = QHBoxLayout(card)
        row.setContentsMargins(14, 8, 8, 8)
        row.setSpacing(8)

        link = QLabel()
        link.setPixmap(icon_pixmap("link", theme.TEXT_FAINT))
        row.addWidget(link)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("Video veya oynatma listesi bağlantısını yapıştır…")
        self.url_edit.setClearButtonEnabled(True)
        self.url_edit.returnPressed.connect(lambda: self._analyze())
        row.addWidget(self.url_edit, 1)

        paste = QPushButton("Yapıştır")
        paste.setObjectName("Ghost")
        paste.setIcon(icon("paste"))
        paste.setIconSize(ICON_SIZE)
        paste.clicked.connect(self._paste)
        row.addWidget(paste)

        self.analyze_button = QPushButton("Analiz et")
        self.analyze_button.setObjectName("Primary")
        self.analyze_button.clicked.connect(lambda: self._analyze())
        row.addWidget(self.analyze_button)
        return card

    def _build_info_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(16)

        self.thumb = QLabel()
        self.thumb.setObjectName("Thumb")
        self.thumb.setFixedSize(168, 94)
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb.setText("önizleme")
        layout.addWidget(self.thumb)

        info = QVBoxLayout()
        info.setSpacing(4)
        self.title_label = QLabel("—")
        self.title_label.setObjectName("H1")
        self.title_label.setWordWrap(True)
        self.meta_label = QLabel("")
        self.meta_label.setObjectName("Muted")
        self.meta_label.setWordWrap(True)
        info.addStretch(1)
        info.addWidget(self.title_label)
        info.addWidget(self.meta_label)
        info.addStretch(1)
        layout.addLayout(info, 1)

        right = QVBoxLayout()
        right.setSpacing(8)
        right.addStretch(1)
        self.preset_combo = QComboBox()
        self.preset_combo.setFixedWidth(250)
        for label, _selector, _audio in PRESETS:
            self.preset_combo.addItem(label)
        self.preset_combo.setCurrentIndex(int(self.config.get("last_preset", 0)))
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        right.addWidget(self.preset_combo)

        self.download_button = QPushButton("İndir")
        self.download_button.setObjectName("Primary")
        self.download_button.setFixedWidth(250)
        self.download_button.setIcon(icon("download", theme.ON_ACCENT))
        self.download_button.setIconSize(ICON_SIZE)
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self._start_download)
        right.addWidget(self.download_button)
        right.addStretch(1)

        layout.addLayout(right, 0)
        return card

    def _build_formats_section(self) -> QWidget:
        widget = QWidget()
        self.formats_section = widget
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        head = QHBoxLayout()
        self.section_label = QLabel("Formatlar")
        self.section_label.setObjectName("Section")
        self.section_hint = QLabel("bir satır seçersen indirme o formatta yapılır")
        self.section_hint.setObjectName("Muted")
        head.addWidget(self.section_label)
        head.addSpacing(8)
        head.addWidget(self.section_hint)
        head.addStretch(1)
        layout.addLayout(head)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Çözünürlük", "Kap", "Video", "Ses", "Boyut", "Not"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(32)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for column in (1, 2, 3, 4, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._on_format_selected)

        self.playlist_panel = PlaylistPanel()
        self.playlist_panel.selection_changed.connect(self._on_playlist_selection)
        self.playlist_panel.single_requested.connect(lambda: self._analyze(single=True))

        self.results = QStackedWidget()
        self.results.addWidget(self.table)
        self.results.addWidget(self.playlist_panel)
        layout.addWidget(self.results, 1)
        return widget

    def _action_button(self, text: str, icon_name: str, slot) -> QPushButton:
        """Dar pencerede de sigsin diye yazi ipucundadir."""
        button = QPushButton()
        button.setObjectName("Icon")
        button.setIcon(icon(icon_name))
        button.setIconSize(ICON_SIZE)
        button.setToolTip(text)
        button.setAccessibleName(text)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(slot)
        return button

    def _build_queue_page(self) -> QWidget:
        page, layout = self._page()

        head = QHBoxLayout()
        head.setSpacing(10)
        title = QLabel("İndirmeler")
        title.setObjectName("Title")
        self.queue_count = QLabel("0")
        self.queue_count.setObjectName("Subtitle")
        head.addWidget(title)
        head.addWidget(self.queue_count, 0, Qt.AlignmentFlag.AlignBottom)
        head.addStretch(1)
        layout.addLayout(head)

        tools = QHBoxLayout()
        tools.setSpacing(6)
        self.filter_group = QButtonGroup(self)
        self.filter_group.setExclusive(True)
        for index, (label, _statuses) in enumerate(FILTERS):
            button = QPushButton(label)
            button.setObjectName("Filter")
            button.setCheckable(True)
            button.setChecked(index == 0)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.filter_group.addButton(button, index)
            tools.addWidget(button)
        self.filter_group.idClicked.connect(lambda _index: self._apply_filter())
        tools.addStretch(1)
        tools.addWidget(
            self._action_button(
                "İndirme klasörünü aç",
                "folder",
                lambda: self._open_path(str(self.config.get("download_dir"))),
            )
        )
        tools.addWidget(self._action_button("Tümünü duraklat", "pause", self.manager.pause_all))
        tools.addWidget(self._action_button("Tümünü sürdür", "play", self.manager.resume_all))
        tools.addWidget(self._action_button("Bitenleri temizle", "clean", self._clear_finished))
        tools.addWidget(self._action_button("Tümünü iptal et", "x", self.manager.cancel_all))
        layout.addLayout(tools)

        self.queue_area = QScrollArea()
        self.queue_area.setWidgetResizable(True)
        self.queue_area.setFrameShape(QFrame.Shape.NoFrame)
        self.queue_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        container.setObjectName("Root")
        self.queue_layout = QVBoxLayout(container)
        self.queue_layout.setContentsMargins(0, 0, 6, 0)
        self.queue_layout.setSpacing(8)
        self.empty_label = EmptyState(
            "inbox", "Henüz indirme yok", "Yeni indirme sayfasından bir bağlantı ekle."
        )
        self.queue_layout.addWidget(self.empty_label, 1)
        self.queue_layout.addStretch(0)
        self.queue_area.setWidget(container)
        layout.addWidget(self.queue_area, 1)
        return page

    # ------------------------------------------------------------- durum
    def _refresh_engine_status(self) -> None:
        if self.engine is None:
            self.engine_chip.setText("motor yok")
            return
        version = self.engine.version() if self.engine.source != "missing" else "yok"
        self.engine_chip.setText(f"yt-dlp {version}")
        self.engine_chip.setToolTip(f"kaynak: {self.engine.source}")

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
        apply_dark_titlebar(self)
        super().showEvent(event)

    def _validate_environment(self) -> None:
        messages: list[str] = []
        ready = self.engine is not None and self.engine.source != "missing"
        if not ready:
            messages.append("yt-dlp bulunamadı. Ayarlar → Araçlar bölümünden kurabilirsin.")
        self.analyze_button.setEnabled(ready)
        if not ready:
            self.download_button.setEnabled(False)

        self.ffmpeg_ver = ffmpeg_version(str(self.config.get("ffmpeg_path") or ""))
        if not self.ffmpeg_dir:
            messages.append(
                "ffmpeg bulunamadı. 1080p gibi ayrı ses+video formatları birleştirilemez. "
                "Ayarlar → Araçlar bölümünden kurabilirsin."
            )
        if not find_js_runtime():
            messages.append(
                "JavaScript ortamı (deno) yok; YouTube'da bazı formatlar eksik kalabilir. "
                "Ayarlar → Araçlar bölümünden kurabilirsin."
            )

        self._env_messages = messages
        self._show_env_banner()

    def _show_env_banner(self) -> None:
        self.banner.setText("\n".join(self._env_messages))
        self.banner.setToolTip("")
        self.banner.setVisible(bool(self._env_messages))

    def _offer_setup(self) -> None:
        missing = missing_tools(self.engine, str(self.config.get("ffmpeg_path") or ""))
        if not missing or self.config.get("setup_dismissed"):
            return
        if SetupDialog(self.config, missing, self).exec():
            self._reload_tools()
            self.statusBar().showMessage("Kurulum tamamlandı")

    def _reload_tools(self) -> None:
        self.ffmpeg_dir = find_ffmpeg(str(self.config.get("ffmpeg_path") or ""))
        self.aria2_exe = find_aria2(str(self.config.get("aria2_path") or ""))
        self.engine = load_engine(str(self.config.get("engine"))) or self.engine
        self.manager.engine = self.engine
        self._refresh_engine_status()
        self._validate_environment()
        self.manager.start()  # es zamanlilik degismis ya da motor yeni kurulmus olabilir

    def _set_info_visible(self, visible: bool) -> None:
        self.info_card.setVisible(visible)
        self.formats_section.setVisible(visible)
        self.welcome.setVisible(not visible)

    # ---------------------------------------------------------- etkilesim
    def _paste(self) -> None:
        text = QGuiApplication.clipboard().text().strip()
        if text:
            self.url_edit.setText(text)
            self._analyze()

    def _on_preset_changed(self, index: int) -> None:
        if self._syncing_preset:
            return
        self.config.set("last_preset", index)
        if index == TABLE_PRESET_INDEX and self.table.currentRow() < 0 and self.table.rowCount() > 0:
            self.table.selectRow(0)

    def _on_format_selected(self) -> None:
        if self._syncing_preset or self.table.currentRow() < 0:
            return
        self._syncing_preset = True
        self.preset_combo.setCurrentIndex(TABLE_PRESET_INDEX)
        self._syncing_preset = False
        self.config.set("last_preset", TABLE_PRESET_INDEX)

    def _analyze(self, single: bool = False) -> None:
        url = self.url_edit.text().strip()
        if not url:
            return
        if self._probe_thread is not None and self._probe_thread.isRunning():
            return  # buton kapali olsa da Enter ve surukle-birak buraya ulasabilir
        if not url.lower().startswith(("http://", "https://")):
            QMessageBox.warning(self, "Geçersiz bağlantı", "Bağlantı http:// veya https:// ile başlamalı.")
            return
        if self.engine is None or self.engine.source == "missing":
            QMessageBox.critical(self, "Motor yok", "yt-dlp bulunamadı. Ayarlar → Araçlar bölümünden kur.")
            return

        self.analyze_button.setEnabled(False)
        self.analyze_button.setText("Analiz ediliyor…")
        self.statusBar().showMessage("Bağlantı çözümleniyor…")
        self.busy_bar.setVisible(True)
        self._show_env_banner()
        self._source_url = url

        self._probe_thread = ProbeThread(
            self.engine, url, str(self.config.get("cookies_browser") or ""), single, self
        )
        self._probe_thread.done.connect(self._on_probe_done)
        self._probe_thread.failed.connect(self._on_probe_failed)
        self._probe_thread.start()

    def _on_probe_done(self, info: MediaInfo) -> None:
        self.info = info
        self.busy_bar.setVisible(False)
        self.analyze_button.setEnabled(True)
        self.analyze_button.setText("Analiz et")

        if info.is_playlist and not info.entries:
            self._on_probe_failed("Bu listede indirilebilecek video bulunamadı.")
            return

        self.title_label.setText(info.title)
        length = f"{len(info.entries)} video" if info.is_playlist else human_duration(info.duration)
        # Liste icin extractor adi ("YoutubeTab") kullaniciya bir sey anlatmiyor.
        meta = [info.uploader, length, "" if info.is_playlist else info.extractor]
        self.meta_label.setText("  ·  ".join(part for part in meta if part))
        self._load_thumbnail(info.thumbnail)

        if info.is_playlist:
            self._show_playlist(info)
        else:
            self._show_formats(info)
        self._set_info_visible(True)

    def _show_formats(self, info: MediaInfo) -> None:
        self._fill_table(info.formats)
        self.results.setCurrentWidget(self.table)
        self.section_label.setText("Formatlar")
        self.section_hint.setText("bir satır seçersen indirme o formatta yapılır")
        self._set_table_preset_enabled(True)
        self.download_button.setText("İndir")
        self.download_button.setEnabled(True)
        self.statusBar().showMessage(f"{len(info.formats)} format bulundu")

    def _show_playlist(self, info: MediaInfo) -> None:
        self._set_table_preset_enabled(False)
        self.results.setCurrentWidget(self.playlist_panel)
        self.section_label.setText("Videolar")
        self.section_hint.setText("indirmek istediklerini işaretle; kalite yukarıdan seçilir")
        known = store.archive_keys() if self.config.get("use_archive") else set()
        self.playlist_panel.load(info, known, self._source_url)
        self.statusBar().showMessage(f"{len(info.entries)} video bulundu")

    def _set_table_preset_enabled(self, enabled: bool) -> None:
        """Tablodan format secimi tek videoya ozgu; listede kapatilir."""
        self.preset_combo.model().item(TABLE_PRESET_INDEX).setEnabled(enabled)
        if not enabled and self.preset_combo.currentIndex() == TABLE_PRESET_INDEX:
            self._syncing_preset = True
            self.preset_combo.setCurrentIndex(0)
            self._syncing_preset = False

    def _on_playlist_selection(self, count: int) -> None:
        self.download_button.setText(f"Seçilenleri indir ({count})")
        self.download_button.setEnabled(count > 0)

    def _on_probe_failed(self, message: str) -> None:
        self.busy_bar.setVisible(False)
        self.analyze_button.setEnabled(True)
        self.analyze_button.setText("Analiz et")
        self.statusBar().showMessage("Analiz başarısız")
        self.banner.setText(explain(message).message)
        self.banner.setToolTip(message)
        self.banner.setVisible(True)

    def _fill_table(self, formats: list[FormatInfo]) -> None:
        self._row_formats.clear()
        self.table.setRowCount(0)

        visible = [f for f in formats if f.ext not in ("mhtml", "json") and f.format_id]
        self.table.setRowCount(len(visible))
        for row, fmt in enumerate(visible):
            self._row_formats[row] = fmt
            values = [
                fmt.format_id,
                fmt.resolution,
                fmt.ext,
                fmt.vcodec.split(".")[0] if fmt.has_video else "—",
                fmt.acodec.split(".")[0] if fmt.has_audio else "—",
                human_size(fmt.filesize),
                fmt.note,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in (1, 2, 3, 4, 5):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, column, item)

        if self.table.rowCount():
            self._syncing_preset = True
            self.table.clearSelection()
            self.table.scrollToTop()
            self._syncing_preset = False

    # ------------------------------------------------------------ indirme
    def _current_selection(self) -> tuple[str, bool] | None:
        index = self.preset_combo.currentIndex()
        if index != TABLE_PRESET_INDEX:
            _label, selector, audio_only = PRESETS[index]
            return selector, audio_only

        row = self.table.currentRow()
        fmt = self._row_formats.get(row)
        if fmt is None:
            return None
        if fmt.has_video and not fmt.has_audio:
            return f"{fmt.format_id}+ba/b", False
        return fmt.format_id, False

    def _start_download(self) -> None:
        if not self.info:
            return
        if self.info.is_playlist:
            self._start_playlist(self.info)
            return
        selection = self._current_selection()
        if not selection or not selection[0]:
            QMessageBox.information(self, "Format seç", "Önce tablodan bir format seç.")
            return
        selector, audio_only = selection

        archive = self._archive_path()
        if archive and store.archive_key(self.info.extractor, self.info.id) in store.archive_keys():
            answer = QMessageBox.question(
                self, "Daha önce indirildi", "Bu video daha önce indirilmiş. Yine de indirilsin mi?"
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            archive = ""

        outdir = str(self.config.get("download_dir"))
        os.makedirs(outdir, exist_ok=True)

        job = self._make_job(self.info.url, self.info.title, selector, audio_only, outdir, archive)
        self._add_jobs([job])
        self._show_page(PAGE_QUEUE)
        self.statusBar().showMessage(f"Kuyruğa eklendi: {job.title}")

    def _start_playlist(self, info: MediaInfo) -> None:
        entries = self.playlist_panel.checked_entries()
        if not entries:
            return
        index = self.preset_combo.currentIndex()
        _label, selector, audio_only = PRESETS[0 if index == TABLE_PRESET_INDEX else index]

        outdir = str(self.config.get("download_dir"))
        if self.config.get("playlist_subfolder"):
            outdir = os.path.join(outdir, safe_folder_name(info.title))
        os.makedirs(outdir, exist_ok=True)

        width = max(2, len(str(len(info.entries))))
        jobs = [
            self._make_job(
                entry.url,
                entry.title,
                selector,
                audio_only,
                outdir,
                self._archive_path(),
                filename_prefix=f"{entry.index:0{width}d} - ",
                playlist=info.title,
            )
            for entry in entries
        ]
        self._add_jobs(jobs)
        self._show_page(PAGE_QUEUE)
        self.statusBar().showMessage(f"{len(jobs)} video kuyruğa eklendi")

    def _archive_path(self) -> str:
        return str(archive_file()) if self.config.get("use_archive") else ""

    def _make_job(
        self,
        url: str,
        title: str,
        selector: str,
        audio_only: bool,
        outdir: str,
        archive: str,
        **extra,
    ) -> Job:
        return Job(
            url=url,
            title=title,
            selector=selector,
            outdir=outdir,
            audio_only=audio_only,
            cookies=str(self.config.get("cookies_browser") or ""),
            ffmpeg_dir=self.ffmpeg_dir,
            merge_format=str(self.config.get("merge_format") or ""),
            write_subs=bool(self.config.get("write_subs")),
            embed_metadata=bool(self.config.get("embed_metadata")),
            archive_file=archive,
            format_sort=PRESET_SORT.get(selector, ""),
            **self._speed_options(),
            **extra,
        )

    def _speed_options(self) -> dict:
        """Ayarlardan gelen hiz parametreleri (tek yerden Job'a aktarilir)."""
        mode = str(self.config.get("external_downloader") or "auto")
        aria2 = self.aria2_exe if mode != "native" else ""
        return {
            "fragments": int(self.config.get("concurrent_fragments") or 1),
            "aria2_exe": aria2 or "",
            "chunk_size": str(self.config.get("http_chunk_size") or ""),
            "throttled_rate": bool(self.config.get("throttled_rate")),
        }

    def _add_jobs(self, jobs: list[Job]) -> None:
        """Isleri, verilen sira kuyrugun en ustunde gorunecek sekilde ekler."""
        self._add_rows(jobs)
        self.manager.add_many(jobs)
        self.queue_area.verticalScrollBar().setValue(0)

    def _add_rows(self, jobs: list[Job]) -> None:
        self.queue_area.setUpdatesEnabled(False)
        for job in reversed(jobs):
            row = JobRow(job, self)
            row.cancel_requested.connect(self.manager.cancel)
            row.open_requested.connect(self._open_job_folder)
            row.pause_requested.connect(self.manager.pause)
            row.resume_requested.connect(self.manager.resume)
            self._job_rows[job.id] = row
            self.queue_layout.insertWidget(0, row)
            row.setVisible(self._matches_filter(job))
        self.queue_area.setUpdatesEnabled(True)
        self.empty_label.setVisible(not self._job_rows)
        self._update_queue_count()

    def _matches_filter(self, job: Job) -> bool:
        _label, statuses = FILTERS[max(0, self.filter_group.checkedId())]
        return not statuses or job.status in statuses

    def _apply_filter(self) -> None:
        for job_id, row in self._job_rows.items():
            row.setVisible(self._matches_filter(self.manager.jobs[job_id]))

    def _restore_queue(self) -> None:
        autostart = bool(self.config.get("resume_on_start", True))
        jobs = self.manager.restore(store.load_queue(), autostart)
        if not jobs:
            return
        # Araclarin yeri onceki oturumdan bu yana degismis olabilir.
        speed = self._speed_options()
        for job in jobs:
            job.ffmpeg_dir = self.ffmpeg_dir
            job.aria2_exe = speed["aria2_exe"]
        self._add_rows(jobs)
        self.manager.start()

    def _clear_finished(self) -> None:
        for job_id in self.manager.remove_finished():
            row = self._job_rows.pop(job_id, None)
            if row:
                self.queue_layout.removeWidget(row)
                row.deleteLater()
        self.empty_label.setVisible(not self._job_rows)
        self._update_queue_count()

    def _open_history(self) -> None:
        dialog = HistoryDialog(self)
        dialog.open_path.connect(self._open_path)
        dialog.download_again.connect(self.analyze_url)
        dialog.exec()

    def analyze_url(self, url: str) -> None:
        self._show_page(PAGE_NEW)
        self.url_edit.setText(url)
        self._analyze()

    def _on_job_changed(self, job_id: str) -> None:
        row = self._job_rows.get(job_id)
        job = self.manager.jobs.get(job_id)
        if row and job:
            row.refresh(job)
            row.setVisible(self._matches_filter(job))
        self._update_queue_count()

    def _update_queue_count(self) -> None:
        total = len(self.manager.jobs)
        active = self.manager.active_count()
        self.queue_count.setText(f"{total} iş · {active} aktif" if total else "")
        waiting = sum(
            job.status in ("queued", "downloading", "merging", "waiting")
            for job in self.manager.jobs.values()
        )
        self.queue_badge.setText(str(waiting))
        self.queue_badge.setVisible(waiting > 0)

    def _open_job_folder(self, job_id: str) -> None:
        job = self.manager.jobs.get(job_id)
        if not job:
            return
        target = job.filepath or job.outdir
        self._open_path(target)

    def _open_path(self, path: str) -> None:
        if not path:
            return
        try:
            if os.path.isdir(path):
                if sys.platform == "win32":
                    os.startfile(path)  # noqa: S606
                else:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            elif os.path.exists(path):
                if sys.platform == "win32":
                    subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
                else:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))
            else:
                self.statusBar().showMessage("Dosya henüz oluşmadı")
        except OSError as exc:
            self.statusBar().showMessage(f"Açılamadı: {exc}")

    # ------------------------------------------------------------- gorsel
    def _load_thumbnail(self, url: str) -> None:
        if self._thumb_reply is not None:
            self._thumb_reply.abort()
            self._thumb_reply = None

        self.thumb.setPixmap(QPixmap())
        self.thumb.setText("önizleme")
        if not url:
            return

        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b"User-Agent", b"Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        reply = self._thumb_manager.get(request)
        self._thumb_reply = reply
        reply.finished.connect(lambda: self._thumbnail_ready(reply))

    def _thumbnail_ready(self, reply: QNetworkReply) -> None:
        if reply is not self._thumb_reply:
            reply.deleteLater()
            return
        self._thumb_reply = None
        data = reply.readAll()
        reply.deleteLater()
        if reply.error() != QNetworkReply.NetworkError.NoError:
            return

        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            return
        self.thumb.setText("")
        self.thumb.setPixmap(
            rounded_thumbnail(pixmap, self.thumb.size(), self.devicePixelRatioF())
        )

    # ------------------------------------------------------------- ayarlar
    def _open_settings(self) -> None:
        if self.engine is None:
            QMessageBox.critical(self, "Motor yok", "Motor tanımı (engines/*.json) bulunamadı.")
            return
        dialog = SettingsDialog(self.config, self.engine, self.ffmpeg_ver, self)
        if dialog.exec():
            self._reload_tools()
            self.statusBar().showMessage("Ayarlar kaydedildi")

    # ------------------------------------------------------- surukle-birak
    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt API
        urls = event.mimeData().urls()
        if not urls:
            return
        self.analyze_url(urls[0].toString())

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        # Acik ag istekleri ve calisan thread'ler Qt nesneleri yikilmadan bitmeli,
        # aksi halde cikista sessiz bir cokme (access violation) olabilir.
        self.config.save()
        self.manager.shutdown()  # calisan isler sonraki acilisa kalir
        reply = self._thumb_reply
        self._thumb_reply = None  # abort() finished sinyalini hemen tetikler
        if reply is not None:
            reply.abort()
            reply.deleteLater()
        if self._probe_thread is not None and self._probe_thread.isRunning():
            self._probe_thread.wait(3000)
        super().closeEvent(event)
