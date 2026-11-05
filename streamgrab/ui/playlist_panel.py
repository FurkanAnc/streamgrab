"""Oynatma listesi / kanal icin isaretlenebilir video tablosu."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.playlist import parse_ranges
from ..core.probe import MediaInfo, PlaylistEntry
from ..core.store import archive_key
from .format import human_duration


class PlaylistPanel(QWidget):
    selection_changed = Signal(int)
    single_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entries: list[PlaylistEntry] = []
        self._loading = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        select_all = QPushButton("Tümünü seç")
        select_all.setObjectName("Ghost")
        select_all.clicked.connect(lambda: self._set_all(True))
        select_none = QPushButton("Hiçbiri")
        select_none.setObjectName("Ghost")
        select_none.clicked.connect(lambda: self._set_all(False))
        bar.addWidget(select_all)
        bar.addWidget(select_none)

        self.range_edit = QLineEdit()
        self.range_edit.setPlaceholderText("Aralık: 1-10, 15, 20-")
        self.range_edit.setFixedWidth(200)
        self.range_edit.returnPressed.connect(self._apply_range)
        bar.addWidget(self.range_edit)
        apply_range = QPushButton("Uygula")
        apply_range.clicked.connect(self._apply_range)
        bar.addWidget(apply_range)

        self.single_button = QPushButton("Sadece bağlantıdaki videoyu aç")
        self.single_button.setObjectName("Ghost")
        self.single_button.clicked.connect(self.single_requested.emit)
        bar.addWidget(self.single_button)

        bar.addStretch(1)
        self.count_label = QLabel("")
        self.count_label.setObjectName("Muted")
        bar.addWidget(self.count_label)
        layout.addLayout(bar)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["", "#", "Başlık", "Süre", "Durum"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(30)
        header = self.table.horizontalHeader()
        for column in (0, 1, 3, 4):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.cellClicked.connect(self._on_cell_clicked)
        layout.addWidget(self.table, 1)

    # -------------------------------------------------------------- yukleme
    def load(self, info: MediaInfo, downloaded: set[str], source_url: str) -> None:
        self._entries = info.entries
        self._loading = True
        self.table.setRowCount(len(info.entries))
        for row, entry in enumerate(info.entries):
            known = archive_key(entry.extractor, entry.id) in downloaded
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            check.setCheckState(
                Qt.CheckState.Checked if entry.available and not known else Qt.CheckState.Unchecked
            )
            self.table.setItem(row, 0, check)

            status = "indirildi" if known else "" if entry.available else "erişilemeyebilir"
            values = [str(entry.index), entry.title, human_duration(entry.duration) or "-", status]
            for column, value in enumerate(values, start=1):
                item = QTableWidgetItem(value)
                if column != 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, column, item)
        self._loading = False

        self.range_edit.clear()
        self.table.scrollToTop()
        # watch?v=X&list=Y gibi bir baglanti hem video hem liste gosterir.
        self.single_button.setVisible(
            any(len(entry.id) >= 6 and entry.id in source_url for entry in info.entries)
        )
        self._emit_count()

    # ------------------------------------------------------------- secim
    def checked_entries(self) -> list[PlaylistEntry]:
        return [
            entry
            for row, entry in enumerate(self._entries)
            if self.table.item(row, 0).checkState() == Qt.CheckState.Checked
        ]

    def _set_rows(self, wanted) -> None:
        self._loading = True
        for row in range(self.table.rowCount()):
            state = Qt.CheckState.Checked if wanted(row) else Qt.CheckState.Unchecked
            self.table.item(row, 0).setCheckState(state)
        self._loading = False
        self._emit_count()

    def _set_all(self, checked: bool) -> None:
        self._set_rows(lambda _row: checked)

    def _apply_range(self) -> None:
        text = self.range_edit.text().strip()
        if not text:
            return
        try:
            numbers = parse_ranges(text, len(self._entries))
        except ValueError:
            self.count_label.setText("Geçersiz aralık. Örnek: 1-10, 15, 20-")
            return
        self._set_rows(lambda row: self._entries[row].index in numbers)

    def _on_cell_clicked(self, row: int, column: int) -> None:
        if column == 0:
            return  # kutunun kendisi zaten degisir
        item = self.table.item(row, 0)
        checked = item.checkState() == Qt.CheckState.Checked
        item.setCheckState(Qt.CheckState.Unchecked if checked else Qt.CheckState.Checked)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if not self._loading and item.column() == 0:
            self._emit_count()

    def _emit_count(self) -> None:
        count = len(self.checked_entries())
        self.count_label.setText(f"{count} / {len(self._entries)} seçili")
        self.selection_changed.emit(count)
