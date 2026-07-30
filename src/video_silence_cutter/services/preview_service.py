import os
import subprocess
import logging
from pathlib import Path
from typing import Optional
from PySide6.QtGui import QImage, QPixmap, QColor, QPainter, QFont, QPen, QBrush
from PySide6.QtCore import Qt, QRect

from ..core.ffmpeg_locator import FFmpegLocator
from ..models.title_settings import TitleSettingsGroup, SingleTitleSettings
from ..services.font_service import FontService

logger = logging.getLogger(__name__)

class PreviewService:
    def __init__(self, locator: FFmpegLocator):
        self.locator = locator
        self.ffmpeg_path = locator.find_ffmpeg()

    def capture_frame(self, video_path: str, timestamp_sec: float, output_image_path: Path) -> bool:
        if not self.ffmpeg_path or not Path(video_path).is_file():
            return False

        cmd = [
            str(self.ffmpeg_path),
            "-y",
            "-ss", f"{timestamp_sec:.2f}",
            "-i", video_path,
            "-vframes", "1",
            "-s", "1280x720",
            "-f", "image2",
            str(output_image_path)
        ]

        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        return res.returncode == 0 and output_image_path.exists()

    def generate_preview_pixmap(
        self,
        base_frame_path: Optional[Path],
        title_settings: TitleSettingsGroup,
        target_width: int = 1280,
        target_height: int = 720
    ) -> QPixmap:
        image = QImage(target_width, target_height, QImage.Format_ARGB32)

        if base_frame_path and base_frame_path.is_file():
            base_img = QImage(str(base_frame_path))
            if not base_img.isNull():
                image = base_img.scaled(target_width, target_height, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            else:
                image.fill(QColor(0, 0, 0))
        else:
            image.fill(QColor(0, 0, 0))

        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        titles = [title_settings.title1, title_settings.title2, title_settings.title3]
        for t_setting in titles:
            if t_setting.enabled and t_setting.text.strip():
                self._draw_title_on_painter(painter, t_setting, target_width, target_height)

        painter.end()
        return QPixmap.fromImage(image)

    def _draw_title_on_painter(
        self,
        painter: QPainter,
        setting: SingleTitleSettings,
        w: int,
        h: int
    ):
        font = QFont(setting.font_family, setting.font_size)
        font.setPixelSize(setting.font_size)
        painter.setFont(font)

        fm = painter.fontMetrics()
        text_rect = fm.boundingRect(setting.text)
        text_w = text_rect.width()
        text_h = text_rect.height()

        # Determine X
        if setting.align_h == "左":
            x = 50
        elif setting.align_h == "右":
            x = w - text_w - 50
        elif setting.align_h == "中央":
            x = (w - text_w) // 2
        else:
            x = setting.x

        # Determine Y
        if setting.align_v in ["上", "中央上部"]:
            y = 60
        elif setting.align_v in ["下", "中央下部"]:
            y = h - text_h - 60
        elif setting.align_v == "中央":
            y = (h - text_h) // 2
        else:
            y = setting.y

        # Draw Background Box if alpha > 0
        if setting.bg_alpha > 0.0:
            bg_col = QColor(setting.bg_color)
            bg_col.setAlphaF(setting.bg_alpha)
            margin = 10
            bg_rect = QRect(x - margin, y - margin, text_w + margin * 2, text_h + margin * 2)
            painter.fillRect(bg_rect, bg_col)

        # Draw Border Text / Main Text
        text_col = QColor(setting.font_color)
        baseline_y = y + fm.ascent()

        if setting.border_width > 0:
            border_col = QColor(setting.border_color)
            for dx in range(-setting.border_width, setting.border_width + 1):
                for dy in range(-setting.border_width, setting.border_width + 1):
                    if dx != 0 or dy != 0:
                        painter.setPen(border_col)
                        painter.drawText(x + dx, baseline_y + dy, setting.text)

        painter.setPen(text_col)
        painter.drawText(x, baseline_y, setting.text)
