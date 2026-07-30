from typing import List
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget, QTableWidgetItem,
    QLabel, QPushButton, QHeaderView
)
from PySide6.QtCore import Qt
from ..models.silence_interval import SilenceInterval
from ..models.keep_interval import KeepInterval
from ..utils.time_utils import seconds_to_hms

class IntervalTableDialog(QDialog):
    def __init__(
        self,
        parent=None,
        original_duration: float = 0.0,
        silences: List[SilenceInterval] = None,
        keeps: List[KeepInterval] = None
    ):
        super().__init__(parent)
        self.setWindowTitle("無音区間・カット解析結果")
        self.resize(650, 480)

        self.silences = silences or []
        self.keeps = keeps or []
        self.original_duration = original_duration

        total_keep_duration = sum(k.duration for k in self.keeps)
        reduced_seconds = max(0.0, original_duration - total_keep_duration)
        ratio = (reduced_seconds / original_duration * 100.0) if original_duration > 0 else 0.0

        layout = QVBoxLayout(self)

        # Summary Header
        summary_text = (
            f"<b>元再生時間:</b> {seconds_to_hms(original_duration, True)} | "
            f"<b>出力予想時間:</b> {seconds_to_hms(total_keep_duration, True)}<br/>"
            f"<b>検出無音数:</b> {len(self.silences)} 件 | "
            f"<b>削減予定:</b> {reduced_seconds:.1f} 秒 ({ratio:.1f}%)"
        )
        lbl_summary = QLabel(summary_text)
        lbl_summary.setTextFormat(Qt.RichText)
        lbl_summary.setStyleSheet("background: #252526; padding: 10px; border-radius: 4px;")
        layout.addWidget(lbl_summary)

        # Tab Widget
        self.tabs = QTabWidget(self)

        # Tab 1: Silence Table
        self.table_silence = QTableWidget()
        self.table_silence.setColumnCount(4)
        self.table_silence.setHorizontalHeaderLabels(["No.", "開始時間", "終了時間", "無音時間"])
        self.table_silence.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._populate_silence_table()
        self.tabs.addTab(self.table_silence, f"検出された無音区間 ({len(self.silences)}件)")

        # Tab 2: Keep Table
        self.table_keep = QTableWidget()
        self.table_keep.setColumnCount(4)
        self.table_keep.setHorizontalHeaderLabels(["No.", "開始時間", "終了時間", "保持時間"])
        self.table_keep.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._populate_keep_table()
        self.tabs.addTab(self.table_keep, f"実際に残す動画区間 ({len(self.keeps)}件)")

        layout.addWidget(self.tabs)

        # Bottom OK button
        btn_close = QPushButton("閉じる")
        btn_close.clicked.connect(self.accept)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def _populate_silence_table(self):
        self.table_silence.setRowCount(len(self.silences))
        for idx, s in enumerate(self.silences):
            self.table_silence.setItem(idx, 0, QTableWidgetItem(str(idx + 1)))
            self.table_silence.setItem(idx, 1, QTableWidgetItem(seconds_to_hms(s.start, True)))
            self.table_silence.setItem(idx, 2, QTableWidgetItem(seconds_to_hms(s.end, True)))
            self.table_silence.setItem(idx, 3, QTableWidgetItem(f"{s.duration:.2f} 秒"))

    def _populate_keep_table(self):
        self.table_keep.setRowCount(len(self.keeps))
        for idx, k in enumerate(self.keeps):
            self.table_keep.setItem(idx, 0, QTableWidgetItem(str(idx + 1)))
            self.table_keep.setItem(idx, 1, QTableWidgetItem(seconds_to_hms(k.start, True)))
            self.table_keep.setItem(idx, 2, QTableWidgetItem(seconds_to_hms(k.end, True)))
            self.table_keep.setItem(idx, 3, QTableWidgetItem(f"{k.duration:.2f} 秒"))
