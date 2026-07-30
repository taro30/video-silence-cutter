import subprocess
import logging
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt
from ..models.process_result import ProcessResult
from ..utils.time_utils import seconds_to_hms

logger = logging.getLogger(__name__)

class CompletionDialog(QDialog):
    def __init__(self, result: ProcessResult, parent=None):
        super().__init__(parent)
        self.setWindowTitle("処理完了")
        self.resize(520, 360)
        self.result = result

        layout = QVBoxLayout(self)

        lbl_header = QLabel("🎉 処理が正常に完了しました！")
        lbl_header.setStyleSheet("font-size: 16px; font-weight: bold; color: #4CAF50; margin-bottom: 10px;")
        layout.addWidget(lbl_header)

        mins = int(result.elapsed_seconds // 60)
        secs = int(result.elapsed_seconds % 60)
        elapsed_str = f"{mins}分{secs}秒" if mins > 0 else f"{secs}秒"

        info_html = f"""
        <table style='width:100%; border-collapse:collapse; font-size:13px;'>
          <tr><td><b>カット前時間:</b></td><td>{seconds_to_hms(result.original_duration, True)}</td></tr>
          <tr><td><b>カット後時間:</b></td><td>{seconds_to_hms(result.output_duration, True)}</td></tr>
          <tr><td><b>削減時間:</b></td><td>{result.reduced_seconds:.1f} 秒</td></tr>
          <tr><td><b>削減率:</b></td><td><b>{result.reduction_ratio * 100.0:.1f}%</b></td></tr>
          <tr><td><b>無音区間件数:</b></td><td>{result.silence_count} 件</td></tr>
          <tr><td><b>処理時間:</b></td><td>{elapsed_str}</td></tr>
          <tr><td><b>解像度:</b></td><td>{result.width} x {result.height} ({result.fps:.2f} fps)</td></tr>
          <tr><td><b>映像/音声:</b></td><td>{result.video_codec} / {result.audio_codec}</td></tr>
          <tr><td><b>出力ファイル:</b></td><td style='word-break:break-all;'>{result.output_file}</td></tr>
        </table>
        """

        lbl_info = QLabel(info_html)
        lbl_info.setTextFormat(Qt.RichText)
        lbl_info.setStyleSheet("background-color: #252526; padding: 12px; border-radius: 6px;")
        layout.addWidget(lbl_info)

        # Buttons
        btn_layout = QHBoxLayout()

        btn_open_video = QPushButton("▶ 動画を開く")
        btn_open_video.clicked.connect(self._open_video)
        btn_layout.addWidget(btn_open_video)

        btn_show_finder = QPushButton("📁 Finderで表示")
        btn_show_finder.clicked.connect(self._show_in_finder)
        btn_layout.addWidget(btn_show_finder)

        btn_layout.addStretch()

        btn_ok = QPushButton("OK")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ok)

        layout.addLayout(btn_layout)

    def _open_video(self):
        try:
            subprocess.run(["open", self.result.output_file], check=False)
        except Exception as e:
            logger.error(f"Failed to open video: {e}")

    def _show_in_finder(self):
        try:
            subprocess.run(["open", "-R", self.result.output_file], check=False)
        except Exception as e:
            logger.error(f"Failed to show in finder: {e}")
