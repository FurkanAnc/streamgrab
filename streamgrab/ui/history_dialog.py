"""Indirme gecmisi penceresi."""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core import store
from .chrome import apply_dark_titlebar
from .format import human_size


class HistoryDialog(QDialog):
    open_path = Signal(str)
    download_again = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Geçmiş")
        self.resize(860, 540)
        self._records = store.load_history()
        self._visible: list[dict] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(12)

        heading = QLabel("İndirme geçmişi")
        heading.setObjectName("Title")
        root.addWidget(heading)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Başlık veya liste adında ara…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._fill)
        root.addWidget(self.search)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Tarih", "Başlık", "Liste", "Boyut"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(30)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self.table.cellDoubleClicked.connect(lambda _row, _column: self._open())
        root.addWidget(self.table, 1)

        self.empty_label = QLabel("Henüz tamamlanmış indirme yok.")
        self.empty_label.setObjectName("Muted")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.empty_label)

        buttons = QHBoxLayout()
        clear = QPushButton("Geçmişi temizle")
        clear.setObjectName("Ghost")
        clear.clicked.connect(self._clear_history)
        reset = QPushButton("Arşivi sıfırla")
        reset.setObjectName("Ghost")
        reset.setToolTip("Daha önce indirilen videolar yeniden indirilebilir olur.")
        reset.clicked.connect(self._clear_archive)
        buttons.addWidget(clear)
        buttons.addWidget(reset)
        buttons.addStretch(1)

        self.open_button = QPushButton("Klasörde göster")
        self.open_button.clicked.connect(self._open)
        self.again_button = QPushButton("Tekrar analiz et")
        self.again_button.clicked.connect(self._again)
        close = QPushButton("Kapat")
        close.setObjectName("Primary")
        close.clicked.connect(self.accept)
        buttons.addWidget(self.open_button)
        buttons.addWidget(self.again_button)
        buttons.addWidget(close)
        root.addLayout(buttons)

        self._fill()

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
        apply_dark_titlebar(self)
        super().showEvent(event)

    def _fill(self) -> None:
        needle = self.search.text().strip().casefold()
        self._visible = [
            record
            for record in self._records
            if needle in f"{record.get('title', '')} {record.get('playlist', '')}".casefold()
        ]
        self.table.setRowCount(len(self._visible))
        for row, record in enumerate(self._visible):
            stamp = time.strftime("%d.%m.%Y %H:%M", time.localtime(float(record.get("time") or 0)))
            values = [
                stamp,
                str(record.get("title") or ""),
                str(record.get("playlist") or ""),
                human_size(float(record.get("size") or 0)),
            ]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
        self.table.setVisible(bool(self._records))
        self.empty_label.setVisible(not self._records)
        self._update_buttons()

    def _selected(self) -> dict | None:
        row = self.table.currentRow()
        return self._visible[row] if 0 <= row < len(self._visible) else None

    def _update_buttons(self) -> None:
        selected = self._selected() is not None
        self.open_button.setEnabled(selected)
        self.again_button.setEnabled(selected)

    def _open(self) -> None:
        record = self._selected()
        if record:
            self.open_path.emit(str(record.get("path") or ""))

    def _again(self) -> None:
        record = self._selected()
        if record and record.get("url"):
            self.download_again.emit(str(record["url"]))
            self.accept()

    def _clear_history(self) -> None:
        answer = QMessageBox.question(
            self, "Geçmişi temizle", "Geçmiş listesi silinsin mi? İndirilen dosyalara dokunulmaz."
        )
        if answer == QMessageBox.StandardButton.Yes:
            store.clear_history()
            self._records = []
            self._fill()

    def _clear_archive(self) -> None:
        answer = QMessageBox.question(
            self,
            "Arşivi sıfırla",
            "Arşiv sıfırlansın mı? Daha önce indirilen videolar artık atlanmaz.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            store.clear_archive()
