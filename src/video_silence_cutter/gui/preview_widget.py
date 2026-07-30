import logging
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent
from PySide6.QtCore import Qt, Signal

logger = logging.getLogger(__name__)

class PreviewWidget(QWidget):
    file_dropped_signal = Signal(str)
    position_changed_signal = Signal(int, int, int)  # (title_index 1..3, x, y)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumSize(480, 270)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("background-color: #1a1a1a; border: 1px solid #333333; border-radius: 4px;")
        self.layout.addWidget(self.label)

        self.current_pixmap: QPixmap = QPixmap(1280, 720)
        self.current_pixmap.fill(Qt.black)
        self.update_display()

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

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path:
                self.file_dropped_signal.emit(file_path)
