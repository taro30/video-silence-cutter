import logging
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QSlider, QLabel, QWidget
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from ..utils.time_utils import seconds_to_hms

logger = logging.getLogger(__name__)

class VideoPlayerDialog(QDialog):
    def __init__(self, video_path: str, title: str = "動画再生確認", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(850, 560)
        self.video_path = video_path

        layout = QVBoxLayout(self)

        # 1. Video Screen Widget
        self.video_widget = QVideoWidget(self)
        self.video_widget.setStyleSheet("background-color: #000000; border-radius: 6px;")
        layout.addWidget(self.video_widget, 1)

        # 2. Media Player Setup
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)

        # 3. Control Panel Layout
        ctrl_layout = QVBoxLayout()

        # Time Slider & Labels
        h_time = QHBoxLayout()
        self.lbl_current_time = QLabel("00:00:00")
        self.slider_time = QSlider(Qt.Horizontal)
        self.slider_time.setRange(0, 0)
        self.slider_time.sliderMoved.connect(self._on_slider_moved)

        self.lbl_total_time = QLabel("00:00:00")

        h_time.addWidget(self.lbl_current_time)
        h_time.addWidget(self.slider_time)
        h_time.addWidget(self.lbl_total_time)
        ctrl_layout.addLayout(h_time)

        # Play / Pause / Stop / Volume Controls
        h_btns = QHBoxLayout()

        self.btn_play = QPushButton("▶ 再生")
        self.btn_play.clicked.connect(self._toggle_play)

        self.btn_stop = QPushButton("⏹ 停止")
        self.btn_stop.clicked.connect(self._stop_video)

        h_btns.addWidget(self.btn_play)
        h_btns.addWidget(self.btn_stop)

        h_btns.addSpacing(20)

        # Volume
        h_btns.addWidget(QLabel("🔊 音量:"))
        self.slider_volume = QSlider(Qt.Horizontal)
        self.slider_volume.setRange(0, 100)
        self.slider_volume.setValue(80)
        self.audio_output.setVolume(0.8)
        self.slider_volume.valueChanged.connect(self._on_volume_changed)
        self.slider_volume.setFixedWidth(100)
        h_btns.addWidget(self.slider_volume)

        h_btns.addStretch()

        btn_close = QPushButton("閉じる")
        btn_close.clicked.connect(self.close)
        h_btns.addWidget(btn_close)

        ctrl_layout.addLayout(h_btns)
        layout.addLayout(ctrl_layout)

        # Connect signals
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)

        # Load Source Video
        if Path(video_path).is_file():
            self.player.setSource(QUrl.fromLocalFile(video_path))
            self.player.play()
            self.btn_play.setText("⏸ 一時停止")

    def _toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
            self.btn_play.setText("▶ 再生")
        else:
            self.player.play()
            self.btn_play.setText("⏸ 一時停止")

    def _stop_video(self):
        self.player.stop()
        self.btn_play.setText("▶ 再生")

    def _on_position_changed(self, position_ms: int):
        if not self.slider_time.isSliderDown():
            self.slider_time.setValue(position_ms)
        sec = position_ms / 1000.0
        self.lbl_current_time.setText(seconds_to_hms(sec))

    def _on_duration_changed(self, duration_ms: int):
        self.slider_time.setRange(0, duration_ms)
        sec = duration_ms / 1000.0
        self.lbl_total_time.setText(seconds_to_hms(sec))

    def _on_slider_moved(self, position_ms: int):
        self.player.setPosition(position_ms)

    def _on_volume_changed(self, val: int):
        self.audio_output.setVolume(val / 100.0)

    def closeEvent(self, event):
        self.player.stop()
        super().closeEvent(event)
