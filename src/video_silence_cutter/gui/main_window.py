import os
import sys
import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTabWidget,
    QLabel, QLineEdit, QPushButton, QCheckBox, QDoubleSpinBox, QSpinBox,
    QComboBox, QProgressBar, QTextEdit, QFileDialog, QMessageBox, QGroupBox,
    QFormLayout, QColorDialog, QApplication
)
from PySide6.QtGui import QAction, QKeySequence, QPixmap, QColor
from PySide6.QtCore import Qt, QTimer, QSize

from ..core.ffmpeg_locator import FFmpegLocator
from ..models.video_info import VideoInfo
from ..models.silence_settings import SilenceSettings
from ..models.title_settings import TitleSettingsGroup, SingleTitleSettings
from ..models.output_settings import OutputSettings
from ..models.process_result import ProcessResult
from ..services.settings_service import SettingsService
from ..services.font_service import FontService
from ..services.process_service import ProcessService
from ..services.preview_service import PreviewService
from ..utils.path_utils import create_temp_dir, get_app_logs_dir
from ..utils.time_utils import seconds_to_hms, hms_to_seconds, validate_hms

from .preview_widget import PreviewWidget
from .interval_table import IntervalTableDialog
from .completion_dialog import CompletionDialog
from .settings_dialog import SettingsDialog
from .video_player_dialog import VideoPlayerDialog
from .worker import SilenceAnalysisWorker, VideoProcessWorker

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self, settings_service: SettingsService):
        super().__init__()
        self.settings_service = settings_service
        self.app_settings = self.settings_service.load_settings()

        self.setWindowTitle("動画無音自動カット＆タイトル合成ツール")
        self.resize(
            self.app_settings.get("window_width", 1440),
            self.app_settings.get("window_height", 900)
        )

        # Service instances
        self.locator = FFmpegLocator(
            custom_ffmpeg=self.app_settings.get("ffmpeg_path"),
            custom_ffprobe=self.app_settings.get("ffprobe_path")
        )

        try:
            self.process_service = ProcessService(self.locator)
        except Exception as e:
            self.process_service = None
            logger.warning(f"ProcessService init warning: {e}")

        self.preview_service = PreviewService(self.locator)

        # Active State
        self.current_video_info: Optional[VideoInfo] = None
        self.current_temp_dir = create_temp_dir()
        self.base_frame_path: Optional[Path] = None
        self.analysis_worker: Optional[SilenceAnalysisWorker] = None
        self.process_worker: Optional[VideoProcessWorker] = None
        self.last_result: Optional[ProcessResult] = None

        self._setup_menu_bar()
        self._init_ui()
        self._apply_theme()
        self._load_ui_from_settings()
        self._check_ffmpeg_on_startup()

    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e2e;
                color: #cdd6f4;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #45475a;
                border-radius: 8px;
                margin-top: 6px;
                padding-top: 10px;
                background-color: #181825;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
                color: #89b4fa;
            }
            QTabWidget::pane {
                border: 1px solid #45475a;
                border-radius: 6px;
                background-color: #181825;
            }
            QTabBar::tab {
                background: #313244;
                color: #cdd6f4;
                padding: 8px 16px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #89b4fa;
                color: #11111b;
                font-weight: bold;
            }
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #45475a;
            }
            QPushButton:pressed {
                background-color: #585b70;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QProgressBar {
                border: 1px solid #45475a;
                border-radius: 6px;
                text-align: center;
                background-color: #313244;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #89b4fa;
                border-radius: 5px;
            }
        """)

    def _setup_menu_bar(self):
        menubar = self.menuBar()

        # File Menu
        menu_file = menubar.addMenu("ファイル")
        act_open = QAction("動画を開く...", self)
        act_open.setShortcut(QKeySequence("Ctrl+O"))
        act_open.triggered.connect(self._browse_input_video)
        menu_file.addAction(act_open)

        act_outdir = QAction("出力先を選択...", self)
        act_outdir.triggered.connect(self._browse_output_dir)
        menu_file.addAction(act_outdir)

        menu_file.addSeparator()
        act_settings = QAction("設定...", self)
        act_settings.setShortcut(QKeySequence("Ctrl+,"))
        act_settings.triggered.connect(self._open_settings_dialog)
        menu_file.addAction(act_settings)

        menu_file.addSeparator()
        act_exit = QAction("終了", self)
        act_exit.setShortcut(QKeySequence("Ctrl+Q"))
        act_exit.triggered.connect(self.close)
        menu_file.addAction(act_exit)

        # Process Menu
        menu_process = menubar.addMenu("処理")
        act_analyze = QAction("無音区間を解析", self)
        act_analyze.setShortcut(QKeySequence("Ctrl+R"))
        act_analyze.triggered.connect(self._on_analyze_clicked)
        menu_process.addAction(act_analyze)

        act_run = QAction("処理を実行", self)
        act_run.setShortcut(QKeySequence("Ctrl+Return"))
        act_run.triggered.connect(self._on_run_clicked)
        menu_process.addAction(act_run)

        act_cancel = QAction("処理をキャンセル", self)
        act_cancel.triggered.connect(self._on_cancel_clicked)
        menu_process.addAction(act_cancel)

        # Help Menu
        menu_help = menubar.addMenu("ヘルプ")
        act_logs = QAction("ログフォルダを開く", self)
        act_logs.triggered.connect(self._open_logs_folder)
        menu_help.addAction(act_logs)

    def _init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 1. Top Bar: Video Select
        top_group = QGroupBox("入力動画ファイル選択", central_widget)
        top_layout = QVBoxLayout(top_group)

        h_select = QHBoxLayout()
        self.txt_input_path = QLineEdit()
        self.txt_input_path.setPlaceholderText("動画ファイルをドラッグ＆ドロップ、または参照ボタンから選択してください")
        self.txt_input_path.editingFinished.connect(self._on_input_path_edited)
        btn_browse = QPushButton("参照...")
        btn_browse.clicked.connect(self._browse_input_video)

        h_select.addWidget(QLabel("入力ファイル:"))
        h_select.addWidget(self.txt_input_path)
        h_select.addWidget(btn_browse)

        self.btn_play_top = QPushButton("▶ アプリ内プレイヤーで元動画を再生")
        self.btn_play_top.setStyleSheet("font-weight: bold; background-color: #2e7d32; color: white; padding: 5px 10px;")
        self.btn_play_top.setEnabled(False)
        self.btn_play_top.clicked.connect(self._play_input_video)
        h_select.addWidget(self.btn_play_top)

        top_layout.addLayout(h_select)

        self.lbl_video_info = QLabel("動画未選択 (動画ファイルを上記にドラッグ＆ドロップしてください)")
        self.lbl_video_info.setStyleSheet("color: #888888; font-size: 12px; margin-top: 4px;")
        top_layout.addWidget(self.lbl_video_info)

        main_layout.addWidget(top_group)

        # 2. Middle Splitter (Left: Controls, Right: Preview)
        self.splitter = QSplitter(Qt.Horizontal, central_widget)

        # Left Controls Panel
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.tabs_controls = QTabWidget()
        self._init_title_tab()
        self._init_silence_tab()
        self._init_output_tab()
        left_layout.addWidget(self.tabs_controls)

        self.splitter.addWidget(left_widget)

        # Right Preview Panel
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        h_prev_top = QHBoxLayout()
        lbl_prev_header = QLabel("<b>動画レイアウトプレビュー (1280x720) - マウスでタイトル移動可能</b>")
        h_prev_top.addWidget(lbl_prev_header)
        h_prev_top.addStretch()
        right_layout.addLayout(h_prev_top)

        # Main Preview Canvas Area
        self.preview_widget = PreviewWidget()
        self.preview_widget.file_dropped_signal.connect(self._load_video_from_path)
        self.preview_widget.title_position_dragged_signal.connect(self._on_title_dragged)
        right_layout.addWidget(self.preview_widget, 1)

        # Player & Timeline Seek Bar Layout Directly Under Preview Canvas
        player_box = QGroupBox("動画タイムライン・再生コントロール", right_widget)
        player_layout = QVBoxLayout(player_box)
        player_layout.setContentsMargins(8, 8, 8, 8)

        # Timeline Slider Line
        h_time_line = QHBoxLayout()

        self.btn_play_preview = QPushButton("▶ 再生")
        self.btn_play_preview.setFixedWidth(80)
        self.btn_play_preview.setStyleSheet("font-weight: bold; background-color: #007ACC; color: white; padding: 4px 8px;")
        self.btn_play_preview.setEnabled(False)
        self.btn_play_preview.clicked.connect(self._toggle_preview_play)
        h_time_line.addWidget(self.btn_play_preview)

        self.btn_stop_preview = QPushButton("⏹ 停止")
        self.btn_stop_preview.setFixedWidth(60)
        self.btn_stop_preview.setEnabled(False)
        self.btn_stop_preview.clicked.connect(self._stop_preview_play)
        h_time_line.addWidget(self.btn_stop_preview)

        self.lbl_seek_curr_time = QLabel("00:00:00")
        h_time_line.addWidget(self.lbl_seek_curr_time)

        # High precision timeline slider bar (0 to 1000)
        self.slider_video_timeline = QSlider(Qt.Horizontal)
        self.slider_video_timeline.setRange(0, 1000)
        self.slider_video_timeline.setValue(0)
        self.slider_video_timeline.setEnabled(False)
        self.slider_video_timeline.sliderMoved.connect(self._on_timeline_slider_moved)
        self.slider_video_timeline.valueChanged.connect(self._on_timeline_slider_changed)
        h_time_line.addWidget(self.slider_video_timeline, 1)

        self.lbl_seek_total_time = QLabel("00:00:00")
        h_time_line.addWidget(self.lbl_seek_total_time)

        h_time_line.addSpacing(10)
        h_time_line.addWidget(QLabel("🔊"))
        self.slider_volume = QSlider(Qt.Horizontal)
        self.slider_volume.setRange(0, 100)
        self.slider_volume.setValue(80)
        self.slider_volume.setFixedWidth(70)
        self.slider_volume.valueChanged.connect(self._on_volume_changed)
        h_time_line.addWidget(self.slider_volume)

        player_layout.addLayout(h_time_line)
        right_layout.addWidget(player_box)

        self.splitter.addWidget(right_widget)
        self.splitter.setSizes(self.app_settings.get("splitter_sizes", [450, 990]))

        main_layout.addWidget(self.splitter, 1)

        # 3. Bottom Control & Progress Bar
        bottom_box = QGroupBox("実行コントロール・進捗", central_widget)
        bottom_layout = QVBoxLayout(bottom_box)

        h_btns = QHBoxLayout()
        self.btn_update_preview = QPushButton("プレビュー更新")
        self.btn_update_preview.clicked.connect(self._update_preview)

        self.btn_analyze = QPushButton("無音区間を解析")
        self.btn_analyze.clicked.connect(self._on_analyze_clicked)

        self.btn_run = QPushButton("無音カット＆タイトル合成を実行")
        self.btn_run.setStyleSheet("font-weight: bold; background-color: #007ACC; color: white; padding: 6px 12px;")
        self.btn_run.clicked.connect(self._on_run_clicked)

        self.btn_cancel = QPushButton("キャンセル")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)

        self.btn_show_finder = QPushButton("Finderで表示")
        self.btn_show_finder.setEnabled(False)
        self.btn_show_finder.clicked.connect(self._show_output_in_finder)

        h_btns.addWidget(self.btn_update_preview)
        h_btns.addWidget(self.btn_analyze)
        h_btns.addWidget(self.btn_run)
        h_btns.addWidget(self.btn_cancel)
        h_btns.addWidget(self.btn_show_finder)

        bottom_layout.addLayout(h_btns)

        h_progress = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.lbl_status = QLabel("待機中")
        self.lbl_status.setMinimumWidth(200)

        h_progress.addWidget(self.progress_bar)
        h_progress.addWidget(self.lbl_status)
        bottom_layout.addLayout(h_progress)

        main_layout.addWidget(bottom_box)

        # 4. Log Output Area
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setMaximumHeight(120)
        self.txt_log.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; font-family: monospace; font-size: 11px;")
        main_layout.addWidget(self.txt_log)

        self._log_message("アプリが起動しました。")

    def _init_title_tab(self):
        tab_titles = QWidget()
        layout = QVBoxLayout(tab_titles)

        self.sub_tabs_title = QTabWidget()

        # Titles 1, 2, 3
        self.title_controls = []
        for i in range(1, 4):
            t_widget, ctrl_dict = self._create_single_title_controls(i)
            self.sub_tabs_title.addTab(t_widget, f"タイトル {i}")
            self.title_controls.append(ctrl_dict)

        layout.addWidget(self.sub_tabs_title)
        self.tabs_controls.addTab(tab_titles, "タイトル設定")

    def _create_single_title_controls(self, index: int):
        widget = QWidget()
        form = QFormLayout(widget)

        chk_enable = QCheckBox("このタイトルを表示する")
        chk_enable.toggled.connect(lambda: self._on_title_setting_changed())

        txt_text = QLineEdit()
        txt_text.textChanged.connect(lambda: self._on_title_setting_changed())

        # Font Family selection
        combo_font = QComboBox()
        font_files = FontService.scan_available_font_files()
        font_families = [
            "Hiragino Sans",
            "Hiragino Kaku Gothic ProN",
            "Hiragino Maru Gothic ProN",
            "Hiragino Mincho ProN",
            "Yu Gothic",
            "Noto Sans CJK JP",
            "Noto Sans JP",
        ]
        # Add found font files
        for f_stem in font_files.keys():
            if f_stem not in font_families:
                font_families.append(f_stem)

        combo_font.addItems(font_families)
        combo_font.currentIndexChanged.connect(lambda: self._on_title_setting_changed())

        combo_align_h = QComboBox()
        combo_align_h.addItems(["中央", "左", "右", "カスタム"])

        combo_align_v = QComboBox()
        combo_align_v.addItems(["上", "中央", "下", "カスタム"])
        if index == 1:
            combo_align_v.setCurrentText("上")
        elif index == 2:
            combo_align_v.setCurrentText("中央")
        else:
            combo_align_v.setCurrentText("下")

        spin_x = QSpinBox()
        spin_x.setRange(0, 1280)
        spin_x.setValue(50 if index == 1 else 0)

        spin_y = QSpinBox()
        spin_y.setRange(0, 720)
        spin_y.setValue(60 if index == 1 else (360 if index == 2 else 600))

        # Auto-switch align to 'カスタム' when X or Y spinbox is user-modified
        def on_x_changed(val):
            combo_align_h.blockSignals(True)
            combo_align_h.setCurrentText("カスタム")
            combo_align_h.blockSignals(False)
            self._on_title_setting_changed()

        def on_y_changed(val):
            combo_align_v.blockSignals(True)
            combo_align_v.setCurrentText("カスタム")
            combo_align_v.blockSignals(False)
            self._on_title_setting_changed()

        spin_x.valueChanged.connect(on_x_changed)
        spin_y.valueChanged.connect(on_y_changed)

        combo_align_h.currentIndexChanged.connect(lambda: self._on_title_setting_changed())
        combo_align_v.currentIndexChanged.connect(lambda: self._on_title_setting_changed())

        spin_size = QSpinBox()
        spin_size.setRange(10, 200)
        spin_size.setValue(48 if index == 1 else (42 if index == 2 else 32))
        spin_size.valueChanged.connect(lambda: self._on_title_setting_changed())

        # Colors
        btn_color = QPushButton("文字色...")
        btn_color.setStyleSheet("background-color: #FFFFFF; color: #000000;")
        btn_color.setProperty("hex_color", "#FFFFFF")
        btn_color.clicked.connect(lambda: self._pick_color(btn_color))

        btn_border_color = QPushButton("縁取り色...")
        btn_border_color.setStyleSheet("background-color: #000000; color: #FFFFFF;")
        btn_border_color.setProperty("hex_color", "#000000")
        btn_border_color.clicked.connect(lambda: self._pick_color(btn_border_color))

        spin_border_width = QSpinBox()
        spin_border_width.setRange(0, 20)
        spin_border_width.setValue(2)
        spin_border_width.valueChanged.connect(lambda: self._on_title_setting_changed())

        # Time range
        spin_start = QDoubleSpinBox()
        spin_start.setRange(0.0, 86400.0)
        spin_start.setValue(0.0)
        spin_start.valueChanged.connect(lambda: self._on_title_setting_changed())

        spin_end = QDoubleSpinBox()
        spin_end.setRange(0.0, 86400.0)
        spin_end.setValue(12.0)
        spin_end.valueChanged.connect(lambda: self._on_title_setting_changed())

        form.addRow(chk_enable)
        form.addRow("テキスト:", txt_text)
        form.addRow("フォント:", combo_font)
        form.addRow("横位置:", combo_align_h)
        form.addRow("縦位置:", combo_align_v)
        form.addRow("カスタム X (px):", spin_x)
        form.addRow("カスタム Y (px):", spin_y)
        form.addRow("フォントサイズ:", spin_size)

        h_col = QHBoxLayout()
        h_col.addWidget(btn_color)
        h_col.addWidget(btn_border_color)
        form.addRow("カラー:", h_col)
        form.addRow("縁取り幅:", spin_border_width)

        h_time = QHBoxLayout()
        h_time.addWidget(QLabel("開始:"))
        h_time.addWidget(spin_start)
        h_time.addWidget(QLabel("終了:"))
        h_time.addWidget(spin_end)
        form.addRow("表示時間 (秒):", h_time)

        ctrls = {
            "chk_enable": chk_enable,
            "txt_text": txt_text,
            "combo_font": combo_font,
            "combo_align_h": combo_align_h,
            "combo_align_v": combo_align_v,
            "spin_x": spin_x,
            "spin_y": spin_y,
            "spin_size": spin_size,
            "btn_color": btn_color,
            "btn_border_color": btn_border_color,
            "spin_border_width": spin_border_width,
            "spin_start": spin_start,
            "spin_end": spin_end,
        }

        return widget, ctrls

    def _init_silence_tab(self):
        tab_silence = QWidget()
        form = QFormLayout(tab_silence)

        self.chk_silence_enable = QCheckBox("無音カットを有効にする")
        self.chk_silence_enable.setChecked(True)

        self.spin_thresh = QDoubleSpinBox()
        self.spin_thresh.setRange(-100.0, 0.0)
        self.spin_thresh.setValue(-30.0)
        self.spin_thresh.setSuffix(" dB")

        self.spin_min_dur = QDoubleSpinBox()
        self.spin_min_dur.setRange(0.1, 60.0)
        self.spin_min_dur.setValue(3.0)
        self.spin_min_dur.setSuffix(" 秒")

        self.spin_padding = QDoubleSpinBox()
        self.spin_padding.setRange(0.0, 10.0)
        self.spin_padding.setValue(0.2)
        self.spin_padding.setSuffix(" 秒")

        self.txt_range_start = QLineEdit("00:00:00")
        self.txt_range_end = QLineEdit("00:00:00")

        form.addRow(self.chk_silence_enable)
        form.addRow("無音判定レベル:", self.spin_thresh)
        form.addRow("最小無音時間:", self.spin_min_dur)
        form.addRow("前後余白:", self.spin_padding)
        form.addRow("処理開始時間 (HH:MM:SS):", self.txt_range_start)
        form.addRow("処理終了時間 (HH:MM:SS):", self.txt_range_end)

        self.tabs_controls.addTab(tab_silence, "無音検出・範囲設定")

    def _init_output_tab(self):
        tab_output = QWidget()
        form = QFormLayout(tab_output)

        self.txt_output_dir = QLineEdit()
        btn_browse_outdir = QPushButton("参照...")
        btn_browse_outdir.clicked.connect(self._browse_output_dir)
        h_dir = QHBoxLayout()
        h_dir.addWidget(self.txt_output_dir)
        h_dir.addWidget(btn_browse_outdir)

        self.txt_output_filename = QLineEdit()

        self.combo_encoder = QComboBox()
        self.combo_encoder.addItem("互換性優先 (libx264)", "libx264")
        self.combo_encoder.addItem("高速処理 (h264_videotoolbox)", "h264_videotoolbox")

        form.addRow("出力フォルダ:", h_dir)
        form.addRow("出力ファイル名:", self.txt_output_filename)
        form.addRow("エンコード方式:", self.combo_encoder)

        self.tabs_controls.addTab(tab_output, "出力設定")

    def _pick_color(self, button: QPushButton):
        curr_hex = button.property("hex_color") or "#FFFFFF"
        color = QColorDialog.getColor(QColor(curr_hex), self, "カラー選択")
        if color.isValid():
            hex_val = color.name().upper()
            button.setProperty("hex_color", hex_val)
            text_color = "#000000" if color.lightness() > 128 else "#FFFFFF"
            button.setStyleSheet(f"background-color: {hex_val}; color: {text_color};")
            self._update_preview()

    def _load_ui_from_settings(self):
        self.spin_thresh.setValue(self.app_settings.get("silence_threshold_db", -30.0))
        self.spin_min_dur.setValue(self.app_settings.get("silence_min_duration", 3.0))
        self.spin_padding.setValue(self.app_settings.get("silence_padding", 0.2))

        # Title settings from app_settings
        for idx in range(1, 4):
            t_key = f"title{idx}"
            if t_key in self.app_settings:
                d = self.app_settings[t_key]
                ctrls = self.title_controls[idx - 1]
                ctrls["chk_enable"].setChecked(d.get("enabled", True))
                ctrls["txt_text"].setText(d.get("text", f"タイトル{idx}"))
                ctrls["spin_size"].setValue(d.get("font_size", 40))

    def _check_ffmpeg_on_startup(self):
        if not self.process_service or not self.locator.find_ffmpeg():
            self._log_message("⚠️ FFmpegが見つかりません。Homebrew等でインストールしてください。")
            QMessageBox.warning(
                self,
                "FFmpeg未検出",
                "FFmpegが見つかりません。Homebrewでインストールするか、設定画面でFFmpegの保存場所を指定してください。"
            )

    def _browse_input_video(self):
        last_dir = self.app_settings.get("last_open_dir") or str(Path.home())
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "動画ファイルを選択",
            last_dir,
            "動画ファイル (*.mp4 *.mov *.m4v *.mkv *.avi)"
        )
        if file_path:
            self.txt_input_path.setText(file_path)
            self._load_video_from_path(file_path)

    def _on_input_path_edited(self):
        path = self.txt_input_path.text().strip()
        if path and Path(path).is_file():
            self._load_video_from_path(path)

    def _on_title_dragged(self, index: int, new_x: int, new_y: int):
        if 1 <= index <= 3:
            ctrls = self.title_controls[index - 1]
            ctrls["combo_align_h"].blockSignals(True)
            ctrls["combo_align_v"].blockSignals(True)
            ctrls["spin_x"].blockSignals(True)
            ctrls["spin_y"].blockSignals(True)

            ctrls["combo_align_h"].setCurrentText("カスタム")
            ctrls["combo_align_v"].setCurrentText("カスタム")
            ctrls["spin_x"].setValue(new_x)
            ctrls["spin_y"].setValue(new_y)

            ctrls["combo_align_h"].blockSignals(False)
            ctrls["combo_align_v"].blockSignals(False)
            ctrls["spin_x"].blockSignals(False)
            ctrls["spin_y"].blockSignals(False)

            self._on_title_setting_changed()

    def _toggle_preview_play(self):
        self.preview_widget.toggle_play_pause()
        if self.preview_widget.player.playbackState() == QMediaPlayer.PlayingState:
            self.btn_play_preview.setText("⏸ 一時停止")
        else:
            self.btn_play_preview.setText("▶ 再生")

    def _stop_preview_play(self):
        self.preview_widget.stop_video()
        self.btn_play_preview.setText("▶ 再生")

    def _on_timeline_slider_moved(self, val: int):
        if self.current_video_info and self.current_video_info.duration_seconds > 0:
            sec = (val / 1000.0) * self.current_video_info.duration_seconds
            self.lbl_seek_curr_time.setText(seconds_to_hms(sec))
            input_path = self.txt_input_path.text().strip()
            if input_path and Path(input_path).is_file():
                frame_png = Path(self.current_temp_dir.name) / f"frame_seek_{val}.png"
                if self.preview_service.capture_frame(input_path, sec, frame_png):
                    self.base_frame_path = frame_png
                    self._update_preview()

    def _on_timeline_slider_changed(self, val: int):
        if not self.slider_video_timeline.isSliderDown():
            self._on_timeline_slider_moved(val)

    def _on_volume_changed(self, val: int):
        self.preview_widget.audio_output.setVolume(val / 100.0)

    def _load_video_from_path(self, file_path: str):
        if not self.process_service:
            return

        self.txt_input_path.setText(file_path)
        self.btn_play_preview.setEnabled(True)
        self.btn_stop_preview.setEnabled(True)
        self.slider_video_timeline.setEnabled(True)
        self.btn_play_top.setEnabled(True)
        self.preview_widget.set_video_source(file_path)
        self.app_settings["last_open_dir"] = str(Path(file_path).parent)
        self.settings_service.save_settings(self.app_settings)

        try:
            v_info = self.process_service.ffprobe_service.inspect_video(file_path)
            self.current_video_info = v_info

            # Display video info text
            info_str = (
                f"<b>ファイル名:</b> {v_info.file_name} | "
                f"<b>解像度:</b> {v_info.width}x{v_info.height} | "
                f"<b>再生時間:</b> {seconds_to_hms(v_info.duration_seconds, True)} | "
                f"<b>fps:</b> {v_info.fps_str} | "
                f"<b>映像:</b> {v_info.video_codec} | "
                f"<b>音声:</b> {v_info.audio_codec or 'なし'}"
            )
            self.lbl_video_info.setText(info_str)
            self.lbl_seek_total_time.setText(seconds_to_hms(v_info.duration_seconds))

            # Auto set range end
            self.txt_range_start.setText("00:00:00")
            self.txt_range_end.setText(seconds_to_hms(v_info.duration_seconds))

            # Auto set default output filename
            out_dir = self.txt_output_dir.text().strip() or str(Path(file_path).parent)
            self.txt_output_dir.setText(out_dir)
            stem = Path(file_path).stem
            self.txt_output_filename.setText(f"{stem}_cut.mp4")

            self._log_message(f"動画を読み込みました: {v_info.file_name} ({v_info.duration_seconds:.1f}s)")

            # Extract preview base frame
            frame_png = Path(self.current_temp_dir.name) / "base_frame.png"
            if self.preview_service.capture_frame(file_path, 1.0, frame_png):
                self.base_frame_path = frame_png
            else:
                self.base_frame_path = None

            self._update_preview()

        except Exception as e:
            self._log_message(f"❌ 動画読み込みエラー: {e}")
            QMessageBox.critical(self, "エラー", f"動画情報を取得できませんでした:\n{e}")

    def _on_title_setting_changed(self):
        t_group = self._collect_title_settings()
        self._update_preview()

    def _update_preview(self):
        t_group = self._collect_title_settings()
        self.preview_widget.set_title_settings(t_group)
        pixmap = self.preview_service.generate_preview_pixmap(self.base_frame_path, t_group)
        self.preview_widget.set_preview_pixmap(pixmap)

    def _load_ui_from_settings(self):
        self.spin_thresh.setValue(self.app_settings.get("silence_threshold_db", -30.0))
        self.spin_min_dur.setValue(self.app_settings.get("silence_min_duration", 3.0))
        self.spin_padding.setValue(self.app_settings.get("silence_padding", 0.2))

        # Title settings from app_settings
        for idx in range(1, 4):
            t_key = f"title{idx}"
            if t_key in self.app_settings:
                d = self.app_settings[t_key]
                ctrls = self.title_controls[idx - 1]

                ctrls["chk_enable"].blockSignals(True)
                ctrls["txt_text"].blockSignals(True)
                ctrls["combo_font"].blockSignals(True)
                ctrls["combo_align_h"].blockSignals(True)
                ctrls["combo_align_v"].blockSignals(True)
                ctrls["spin_x"].blockSignals(True)
                ctrls["spin_y"].blockSignals(True)
                ctrls["spin_size"].blockSignals(True)

                ctrls["chk_enable"].setChecked(d.get("enabled", True))
                ctrls["txt_text"].setText(d.get("text", f"タイトル{idx}"))

                # Restore font
                font_fam = d.get("font_family", "Hiragino Sans")
                idx_f = ctrls["combo_font"].findText(font_fam)
                if idx_f >= 0:
                    ctrls["combo_font"].setCurrentIndex(idx_f)

                # Restore position presets & custom coords
                align_h = d.get("align_h", "中央")
                align_v = d.get("align_v", "中央上部" if idx == 1 else ("中央" if idx == 2 else "中央下部"))
                idx_h = ctrls["combo_align_h"].findText(align_h)
                if idx_h >= 0:
                    ctrls["combo_align_h"].setCurrentIndex(idx_h)

                idx_v = ctrls["combo_align_v"].findText(align_v)
                if idx_v >= 0:
                    ctrls["combo_align_v"].setCurrentIndex(idx_v)

                ctrls["spin_x"].setValue(d.get("x", 0))
                ctrls["spin_y"].setValue(d.get("y", 0))
                ctrls["spin_size"].setValue(d.get("font_size", 48 if idx == 1 else (42 if idx == 2 else 32)))

                # Restore colors
                f_color = d.get("font_color", "#FFFFFF")
                ctrls["btn_color"].setProperty("hex_color", f_color)
                ctrls["btn_color"].setStyleSheet(f"background-color: {f_color}; color: {'#000000' if QColor(f_color).lightness() > 128 else '#FFFFFF'};")

                b_color = d.get("border_color", "#000000")
                ctrls["btn_border_color"].setProperty("hex_color", b_color)
                ctrls["btn_border_color"].setStyleSheet(f"background-color: {b_color}; color: {'#000000' if QColor(b_color).lightness() > 128 else '#FFFFFF'};")

                ctrls["chk_enable"].blockSignals(False)
                ctrls["txt_text"].blockSignals(False)
                ctrls["combo_font"].blockSignals(False)
                ctrls["combo_align_h"].blockSignals(False)
                ctrls["combo_align_v"].blockSignals(False)
                ctrls["spin_x"].blockSignals(False)
                ctrls["spin_y"].blockSignals(False)
                ctrls["spin_size"].blockSignals(False)

    def _collect_title_settings(self) -> TitleSettingsGroup:
        titles = []
        for idx, ctrls in enumerate(self.title_controls, start=1):
            st = SingleTitleSettings(
                enabled=ctrls["chk_enable"].isChecked(),
                text=ctrls["txt_text"].text(),
                align_h=ctrls["combo_align_h"].currentText(),
                align_v=ctrls["combo_align_v"].currentText(),
                x=ctrls["spin_x"].value(),
                y=ctrls["spin_y"].value(),
                font_family=ctrls["combo_font"].currentText(),
                font_size=ctrls["spin_size"].value(),
                font_color=ctrls["btn_color"].property("hex_color") or "#FFFFFF",
                border_color=ctrls["btn_border_color"].property("hex_color") or "#000000",
                border_width=ctrls["spin_border_width"].value(),
                start_time=ctrls["spin_start"].value(),
                end_time=ctrls["spin_end"].value()
            )
            titles.append(st)

            # Update app_settings dictionary for persistent storage
            t_key = f"title{idx}"
            self.app_settings[t_key] = {
                "enabled": st.enabled,
                "text": st.text,
                "align_h": st.align_h,
                "align_v": st.align_v,
                "x": st.x,
                "y": st.y,
                "font_family": st.font_family,
                "font_size": st.font_size,
                "font_color": st.font_color,
                "border_color": st.border_color,
                "border_width": st.border_width,
                "start_time": st.start_time,
                "end_time": st.end_time,
            }

        # Auto save settings
        self.settings_service.save_settings(self.app_settings)
        return TitleSettingsGroup(title1=titles[0], title2=titles[1], title3=titles[2])

    def _collect_silence_settings(self) -> SilenceSettings:
        start_sec = 0.0
        end_sec = 0.0
        if validate_hms(self.txt_range_start.text()):
            start_sec = hms_to_seconds(self.txt_range_start.text())
        if validate_hms(self.txt_range_end.text()):
            end_sec = hms_to_seconds(self.txt_range_end.text())

        return SilenceSettings(
            enabled=self.chk_silence_enable.isChecked(),
            threshold_db=self.spin_thresh.value(),
            min_duration=self.spin_min_dur.value(),
            padding=self.spin_padding.value(),
            range_start=start_sec,
            range_end=end_sec
        )

    def _on_analyze_clicked(self):
        input_path = self.txt_input_path.text().strip()
        if not input_path or not Path(input_path).is_file():
            QMessageBox.warning(self, "警告", "入力動画ファイルを選択してください。")
            return

        self._set_processing_ui_state(True)
        self._log_message("無音区間の解析を開始しました...")

        sil_settings = self._collect_silence_settings()
        self.analysis_worker = SilenceAnalysisWorker(self.process_service, input_path, sil_settings)
        self.analysis_worker.progress_signal.connect(lambda pct, msg: self._update_progress(pct, msg))
        self.analysis_worker.finished_signal.connect(self._on_analysis_finished)
        self.analysis_worker.error_signal.connect(self._on_process_error)
        self.analysis_worker.start()

    def _on_analysis_finished(self, v_info, silences, keeps):
        self._set_processing_ui_state(False)
        self._log_message(f"無音解析完了: 検出無音数={len(silences)}件, 保持区間数={len(keeps)}件")

        dlg = IntervalTableDialog(self, v_info.duration_seconds, silences, keeps)
        dlg.exec()

    def _on_run_clicked(self):
        input_path = self.txt_input_path.text().strip()
        out_dir = self.txt_output_dir.text().strip()
        out_filename = self.txt_output_filename.text().strip()

        if not input_path or not Path(input_path).is_file():
            QMessageBox.warning(self, "警告", "入力動画ファイルが存在しません。")
            return

        if not out_dir or not out_filename:
            QMessageBox.warning(self, "警告", "出力ファイルパスを指定してください。")
            return

        output_path = str(Path(out_dir) / out_filename)

        if input_path == output_path:
            QMessageBox.warning(self, "警告", "入力ファイルと出力ファイルに同じパスを指定できません。")
            return

        if Path(output_path).exists():
            reply = QMessageBox.question(
                self,
                "上書き確認",
                f"出力ファイル '{out_filename}' は既に存在します。上書きしますか？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        sil_settings = self._collect_silence_settings()
        title_settings = self._collect_title_settings()
        out_settings = OutputSettings(
            output_dir=out_dir,
            output_filename=out_filename,
            encoder=self.combo_encoder.currentData()
        )

        self._set_processing_ui_state(True)
        self._log_message(f"処理を開始します: {out_filename}")

        self.process_worker = VideoProcessWorker(
            self.process_service,
            input_path,
            output_path,
            sil_settings,
            title_settings,
            out_settings
        )
        self.process_worker.progress_signal.connect(self._update_progress_full)
        self.process_worker.finished_signal.connect(self._on_process_finished)
        self.process_worker.error_signal.connect(self._on_process_error)
        self.process_worker.start()

    def _on_cancel_clicked(self):
        if self.process_worker:
            self._log_message("処理キャンセルを要請中...")
            self.process_worker.cancel()

    def _on_process_finished(self, result: ProcessResult):
        self._set_processing_ui_state(False)
        self.last_result = result
        self.btn_show_finder.setEnabled(True)

        self._log_message(f"🎉 処理完了: 削減秒数={result.reduced_seconds:.1f}s ({result.reduction_ratio*100:.1f}%)")

        dlg = CompletionDialog(result, self)
        dlg.exec()

    def _on_process_error(self, err_msg: str):
        self._set_processing_ui_state(False)
        self._log_message(f"❌ エラー発生: {err_msg}")
        QMessageBox.critical(self, "処理エラー", f"エラーが発生しました:\n{err_msg}")

    def _set_processing_ui_state(self, is_processing: bool):
        self.btn_run.setEnabled(not is_processing)
        self.btn_analyze.setEnabled(not is_processing)
        self.btn_cancel.setEnabled(is_processing)

    def _update_progress(self, pct: float, msg: str):
        self.progress_bar.setValue(int(pct))
        self.lbl_status.setText(msg)

    def _update_progress_full(self, pct: float, msg: str, elapsed: float, eta: float):
        self.progress_bar.setValue(int(pct))
        eta_str = seconds_to_hms(eta) if eta > 0 else "--:--:--"
        self.lbl_status.setText(f"{msg} (経過: {seconds_to_hms(elapsed)} / 残り: {eta_str})")

    def _browse_output_dir(self):
        curr = self.txt_output_dir.text().strip() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "出力先フォルダを選択", curr)
        if chosen:
            self.txt_output_dir.setText(chosen)

    def _show_output_in_finder(self):
        if self.last_result and self.last_result.output_file:
            subprocess.run(["open", "-R", self.last_result.output_file], check=False)

    def _open_settings_dialog(self):
        dlg = SettingsDialog(self.app_settings, self)
        if dlg.exec():
            self.app_settings = dlg.get_updated_settings()
            self.settings_service.save_settings(self.app_settings)
            self._log_message("設定を更新しました。")

    def _open_logs_folder(self):
        logs_dir = get_app_logs_dir()
        subprocess.run(["open", str(logs_dir)], check=False)

    def _log_message(self, msg: str):
        logger.info(msg)
        self.txt_log.append(f"• {msg}")

    def closeEvent(self, event):
        # Save window size and splitter position
        self.app_settings["window_width"] = self.width()
        self.app_settings["window_height"] = self.height()
        self.app_settings["splitter_sizes"] = self.splitter.sizes()
        self.settings_service.save_settings(self.app_settings)

        if self.current_temp_dir:
            self.current_temp_dir.cleanup()
        event.accept()
