import logging
from pathlib import Path
from typing import Optional, Tuple
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QSlider, QStackedWidget
)
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QMouseEvent
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

from ..models.title_settings import TitleSettingsGroup, SingleTitleSettings
from ..utils.time_utils import seconds_to_hms

logger = logging.getLogger(__name__)

class PreviewWidget(QWidget):
    file_dropped_signal = Signal(str)
    title_position_dragged_signal = Signal(int, int, int)  # (title_index 1..3, new_x, new_y)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumSize(480, 270)

        main_v_layout = QVBoxLayout(self)
        main_v_layout.setContentsMargins(0, 0, 0, 0)

        # 1. Stacked View (Static Preview Frame vs Live Video Player)
        self.stack = QStackedWidget(self)

        # Page 0: Static Title Drag Preview Label
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self._set_default_style()
        self.stack.addWidget(self.label)

        # Page 1: Direct Video Screen
        self.video_screen = QVideoWidget(self)
        self.video_screen.setStyleSheet("background-color: #000000; border-radius: 8px;")
        self.stack.addWidget(self.video_screen)

        main_v_layout.addWidget(self.stack, 1)

        # Note: Playback controls are unified in main_window.py directly under preview panel


        # 3. Setup QMediaPlayer
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_screen)

        self.audio_output.setVolume(0.8)

        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)

        self.current_pixmap: QPixmap = QPixmap(1280, 720)
        self.current_pixmap.fill(Qt.black)

        self.title_settings: Optional[TitleSettingsGroup] = None
        self.video_path: Optional[str] = None
        self.dragging_title_index: Optional[int] = None
        self.drag_start_pos: Optional[QPointF] = None
        self.title_start_x: int = 0
        self.title_start_y: int = 0

        self.update_display()

    def set_video_source(self, video_path: str):
        self.video_path = video_path
        if Path(video_path).is_file():
            self.player.setSource(QUrl.fromLocalFile(video_path))

    def toggle_play_pause(self):
        if not self.video_path or not Path(self.video_path).is_file():
            return

        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
            # Return to title editing preview frame
            self.stack.setCurrentIndex(0)
        else:
            self.stack.setCurrentIndex(1)
            self.player.play()

    def stop_video(self):
        self.player.stop()
        self.stack.setCurrentIndex(0)

    def _on_position_changed(self, position_ms: int):
        pass

    def _on_duration_changed(self, duration_ms: int):
        pass

    def _on_slider_moved(self, position_ms: int):
        self.player.setPosition(position_ms)

    def _on_volume_changed(self, val: int):
        self.audio_output.setVolume(val / 100.0)

    def set_title_settings(self, title_settings: TitleSettingsGroup):
        self.title_settings = title_settings

    def _set_default_style(self):
        self.label.setStyleSheet(
            "background-color: #18181b; "
            "border: 2px dashed #3f3f46; "
            "border-radius: 8px;"
        )

    def _set_active_drag_style(self):
        self.label.setStyleSheet(
            "background-color: #27272a; "
            "border: 2px dashed #007acc; "
            "border-radius: 8px;"
        )

    def set_preview_pixmap(self, pixmap: QPixmap):
        self.current_pixmap = pixmap
        self.update_display()

    def update_display(self):
        if not self.current_pixmap.isNull():
            scaled = self.current_pixmap.scaled(
                self.label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.label.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_display()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_active_drag_style()

    def dragLeaveEvent(self, event):
        self._set_default_style()
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent):
        self._set_default_style()
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path:
                self.file_dropped_signal.emit(file_path)

    # --- Mouse Dragging Support for Title Positioning ---

    def _get_canvas_scaling(self) -> Tuple[float, float, float, float]:
        if self.current_pixmap.isNull() or self.label.width() <= 0 or self.label.height() <= 0:
            return 0.0, 0.0, 1.0, 1.0

        pix_w = self.current_pixmap.width()
        pix_h = self.current_pixmap.height()

        lbl_w = self.label.width()
        lbl_h = self.label.height()

        scale = min(lbl_w / pix_w, lbl_h / pix_h)
        scaled_w = pix_w * scale
        scaled_h = pix_h * scale

        offset_x = (lbl_w - scaled_w) / 2.0
        offset_y = (lbl_h - scaled_h) / 2.0

        return offset_x, offset_y, scaled_w, scaled_h

    def _window_pos_to_1280_coords(self, pos: QPointF) -> Optional[Tuple[int, int]]:
        offset_x, offset_y, scaled_w, scaled_h = self._get_canvas_scaling()

        lbl_pos = self.label.mapFrom(self, pos.toPoint())
        lx = lbl_pos.x() - offset_x
        ly = lbl_pos.y() - offset_y

        if lx < 0 or lx > scaled_w or ly < 0 or ly > scaled_h:
            return None

        norm_x = lx / scaled_w
        norm_y = ly / scaled_h

        canvas_x = int(round(norm_x * 1280))
        canvas_y = int(round(norm_y * 720))

        return max(0, min(1280, canvas_x)), max(0, min(720, canvas_y))

    def mousePressEvent(self, event: QMouseEvent):
        if self.stack.currentIndex() == 0 and event.button() == Qt.LeftButton and self.title_settings:
            coords = self._window_pos_to_1280_coords(event.position())
            if coords:
                cx, cy = coords
                titles = [
                    (1, self.title_settings.title1),
                    (2, self.title_settings.title2),
                    (3, self.title_settings.title3),
                ]

                closest_idx = None
                min_dist = 999999.0

                for idx, t in titles:
                    if t.enabled and t.text.strip():
                        tx = t.x if t.align_h == "カスタム" else 640
                        ty = t.y if t.align_v == "カスタム" else (60 if idx == 1 else (360 if idx == 2 else 660))

                        dist = ((cx - tx) ** 2 + (cy - ty) ** 2) ** 0.5
                        if dist < min_dist and dist < 300:
                            min_dist = dist
                            closest_idx = idx

                if closest_idx:
                    self.dragging_title_index = closest_idx
                    self.drag_start_pos = event.position()
                    t_target = getattr(self.title_settings, f"title{closest_idx}")
                    self.title_start_x = t_target.x if t_target.align_h == "カスタム" else (
                        50 if t_target.align_h == "左" else (1230 if t_target.align_h == "右" else 640)
                    )
                    self.title_start_y = t_target.y if t_target.align_v == "カスタム" else (
                        60 if t_target.align_v in ["上", "中央上部"] else (660 if t_target.align_v in ["下", "中央下部"] else 360)
                    )
                    return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.stack.currentIndex() == 0 and self.dragging_title_index and self.drag_start_pos:
            offset_x, offset_y, scaled_w, scaled_h = self._get_canvas_scaling()
            if scaled_w > 0 and scaled_h > 0:
                delta_lbl_x = event.position().x() - self.drag_start_pos.x()
                delta_lbl_y = event.position().y() - self.drag_start_pos.y()

                delta_canvas_x = int(round((delta_lbl_x / scaled_w) * 1280))
                delta_canvas_y = int(round((delta_lbl_y / scaled_h) * 720))

                new_x = max(0, min(1280, self.title_start_x + delta_canvas_x))
                new_y = max(0, min(720, self.title_start_y + delta_canvas_y))

                self.title_position_dragged_signal.emit(self.dragging_title_index, new_x, new_y)
                return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.dragging_title_index = None
            self.drag_start_pos = None

        super().mouseReleaseEvent(event)
