from typing import Any, Dict
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QSpinBox, QDoubleSpinBox,
    QCheckBox, QComboBox, QPushButton, QFileDialog, QGroupBox, QMessageBox
)
from ..services.font_service import FontService

class SettingsDialog(QDialog):
    def __init__(self, settings: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.setWindowTitle("環境・アプリ設定")
        self.resize(550, 480)
        self.settings = dict(settings)

        layout = QVBoxLayout(self)

        # 1. FFmpeg Paths Group
        grp_ffmpeg = QGroupBox("FFmpeg / ffprobe パス指定", self)
        form_ffmpeg = QFormLayout(grp_ffmpeg)

        self.txt_ffmpeg = QLineEdit(self.settings.get("ffmpeg_path", ""))
        btn_browse_ffmpeg = QPushButton("参照...")
        btn_browse_ffmpeg.clicked.connect(self._browse_ffmpeg)
        h_ffmpeg = QHBoxLayout()
        h_ffmpeg.addWidget(self.txt_ffmpeg)
        h_ffmpeg.addWidget(btn_browse_ffmpeg)
        form_ffmpeg.addRow("FFmpeg パス:", h_ffmpeg)

        self.txt_ffprobe = QLineEdit(self.settings.get("ffprobe_path", ""))
        btn_browse_ffprobe = QPushButton("参照...")
        btn_browse_ffprobe.clicked.connect(self._browse_ffprobe)
        h_ffprobe = QHBoxLayout()
        h_ffprobe.addWidget(self.txt_ffprobe)
        h_ffprobe.addWidget(btn_browse_ffprobe)
        form_ffmpeg.addRow("ffprobe パス:", h_ffprobe)

        layout.addWidget(grp_ffmpeg)

        # 2. Defaults Group
        grp_defaults = QGroupBox("処理の既定値", self)
        form_def = QFormLayout(grp_defaults)

        self.spin_thresh = QDoubleSpinBox()
        self.spin_thresh.setRange(-100.0, 0.0)
        self.spin_thresh.setSingleStep(0.5)
        self.spin_thresh.setSuffix(" dB")
        self.spin_thresh.setValue(self.settings.get("silence_threshold_db", -30.0))
        form_def.addRow("無音判定レベル:", self.spin_thresh)

        self.spin_min_dur = QDoubleSpinBox()
        self.spin_min_dur.setRange(0.1, 60.0)
        self.spin_min_dur.setSingleStep(0.1)
        self.spin_min_dur.setSuffix(" 秒")
        self.spin_min_dur.setValue(self.settings.get("silence_min_duration", 3.0))
        form_def.addRow("最小無音時間:", self.spin_min_dur)

        self.spin_pad = QDoubleSpinBox()
        self.spin_pad.setRange(0.0, 10.0)
        self.spin_pad.setSingleStep(0.05)
        self.spin_pad.setSuffix(" 秒")
        self.spin_pad.setValue(self.settings.get("silence_padding", 0.2))
        form_def.addRow("前後余白:", self.spin_pad)

        self.combo_encoder = QComboBox()
        self.combo_encoder.addItem("高速処理 (libx264) [推奨・マルチコア]", "libx264")
        self.combo_encoder.addItem("省電力 (h264_videotoolbox) [ハードウェア加速・低CPU]", "h264_videotoolbox")
        enc_curr = self.settings.get("encoder_mode", "libx264")
        idx_enc = self.combo_encoder.findData(enc_curr)
        if idx_enc >= 0:
            self.combo_encoder.setCurrentIndex(idx_enc)
        form_def.addRow("エンコード方式:", self.combo_encoder)

        layout.addWidget(grp_defaults)

        # 3. Actions / Checkboxes
        grp_opts = QGroupBox("完了後動作", self)
        v_opts = QVBoxLayout(grp_opts)
        self.chk_finder = QCheckBox("処理完了後にFinderで表示する")
        self.chk_finder.setChecked(self.settings.get("open_finder_on_complete", True))
        v_opts.addWidget(self.chk_finder)

        self.chk_open_vid = QCheckBox("処理完了後に動画を開く")
        self.chk_open_vid.setChecked(self.settings.get("open_video_on_complete", False))
        v_opts.addWidget(self.chk_open_vid)

        layout.addWidget(grp_opts)

        # Dialog Buttons
        btn_layout = QHBoxLayout()
        btn_reset = QPushButton("初期設定に戻す")
        btn_reset.clicked.connect(self._reset_defaults)
        btn_layout.addWidget(btn_reset)

        btn_layout.addStretch()

        btn_cancel = QPushButton("キャンセル")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton("保存")
        btn_save.setDefault(True)
        btn_save.clicked.connect(self._save)
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)

    def _browse_ffmpeg(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "FFmpeg バイナリを選択")
        if file_path:
            self.txt_ffmpeg.setText(file_path)

    def _browse_ffprobe(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "ffprobe バイナリを選択")
        if file_path:
            self.txt_ffprobe.setText(file_path)

    def _reset_defaults(self):
        self.spin_thresh.setValue(-30.0)
        self.spin_min_dur.setValue(3.0)
        self.spin_pad.setValue(0.2)
        self.combo_encoder.setCurrentIndex(0)
        self.chk_finder.setChecked(True)
        self.chk_open_vid.setChecked(False)

    def _save(self):
        self.settings["ffmpeg_path"] = self.txt_ffmpeg.text().strip()
        self.settings["ffprobe_path"] = self.txt_ffprobe.text().strip()
        self.settings["silence_threshold_db"] = self.spin_thresh.value()
        self.settings["silence_min_duration"] = self.spin_min_dur.value()
        self.settings["silence_padding"] = self.spin_pad.value()
        self.settings["encoder_mode"] = self.combo_encoder.currentData()
        self.settings["open_finder_on_complete"] = self.chk_finder.isChecked()
        self.settings["open_video_on_complete"] = self.chk_open_vid.isChecked()
        self.accept()

    def get_updated_settings(self) -> Dict[str, Any]:
        return self.settings
