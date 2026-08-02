import logging
from typing import List, Tuple
from PySide6.QtWidgets import QSlider
from PySide6.QtGui import QPainter, QBrush, QPen, QColor
from PySide6.QtCore import Qt, Signal

logger = logging.getLogger(__name__)

class TrimmingSlider(QSlider):
    """
    トリミング開始点・終了点をスライダーバー上に視覚的にマーカー表示＆ハイライト表示し、
    音声発生箇所（有音区間）の視覚化バーおよびCtrl+ホイールズームにも対応したカスタムスライダー
    """
    zoom_changed_signal = Signal(float)

    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self.start_sec = 0.0
        self.end_sec = 0.0
        self.duration_sec = 0.0
        self.zoom_factor = 1.0  # 1.0x 〜 10.0x
        self.view_start_pct = 0.0
        self.audio_intervals: List[Tuple[float, float]] = []  # 有音（音声あり）区間リスト

    def set_trim_range(self, start_sec: float, end_sec: float, duration_sec: float):
        self.start_sec = start_sec
        self.end_sec = end_sec
        self.duration_sec = duration_sec
        self.update()

    def set_audio_presence_intervals(self, audio_intervals: List[Tuple[float, float]]):
        self.audio_intervals = audio_intervals
        self.update()

    def set_zoom_factor(self, factor: float):
        self.zoom_factor = max(1.0, min(10.0, factor))
        self.update()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta != 0:
            step = 1.2 if delta > 0 else 0.8
            new_zoom = max(1.0, min(10.0, self.zoom_factor * step))
            if new_zoom != self.zoom_factor:
                self.zoom_factor = new_zoom
                self.zoom_changed_signal.emit(self.zoom_factor)
                self.update()
                event.accept()
                return
        super().wheelEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.duration_sec <= 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        cy = h // 2

        margin = 12
        groove_w = w - margin * 2
        if groove_w <= 0:
            return

        # ── 0. 音声発生箇所（有音区間）の描画（スライダー直下のインジケーター帯） ──
        if self.audio_intervals:
            painter.setBrush(QBrush(QColor(56, 189, 248, 180)))  # 鮮やかなシアンブルー (音声あり)
            painter.setPen(Qt.NoPen)
            for a_start, a_end in self.audio_intervals:
                st_pct = max(0.0, min(1.0, a_start / self.duration_sec))
                et_pct = max(0.0, min(1.0, a_end / self.duration_sec))
                ax1 = margin + int(st_pct * groove_w)
                ax2 = margin + int(et_pct * groove_w)
                aw = max(2, ax2 - ax1)
                # スライダー溝のすぐ下(cy+6)に音声バーを描画
                painter.drawRoundedRect(ax1, cy + 6, aw, 4, 2, 2)

        has_start = self.start_sec > 0.0
        has_end = 0.0 < self.end_sec < self.duration_sec

        if not (has_start or has_end):
            return

        # ズームに応じたパーセンテージ計算
        s_pct = max(0.0, min(1.0, self.start_sec / self.duration_sec)) if has_start else 0.0
        e_pct = max(0.0, min(1.0, self.end_sec / self.duration_sec)) if has_end else 1.0

        sx = margin + int(s_pct * groove_w)
        ex = margin + int(e_pct * groove_w)

        # ── 1. トリム有効領域のハイライト帯（明るいエメラルドグリーン） ──
        painter.setBrush(QBrush(QColor(0, 230, 118, 150)))
        painter.setPen(Qt.NoPen)
        band_w = max(4, ex - sx)
        painter.drawRoundedRect(sx, cy - 5, band_w, 10, 3, 3)

        # ── 2. 開始点マーカー 🟢 ──
        if has_start:
            painter.setBrush(QBrush(QColor('#00E676')))
            painter.setPen(QPen(QColor('#FFFFFF'), 2))
            painter.drawRoundedRect(sx - 4, cy - 10, 8, 20, 2, 2)

        # ── 3. 終了点マーカー 🔴 ──
        if has_end:
            painter.setBrush(QBrush(QColor('#FF5252')))
            painter.setPen(QPen(QColor('#FFFFFF'), 2))
            painter.drawRoundedRect(ex - 4, cy - 10, 8, 20, 2, 2)
