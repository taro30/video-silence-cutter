import os
import subprocess
import logging
from pathlib import Path
from typing import List, Optional, Callable
from ..models.silence_interval import SilenceInterval
from ..models.silence_settings import SilenceSettings
from ..core.silence_parser import SilenceParser
from ..utils.process_utils import kill_process_group

logger = logging.getLogger(__name__)

class SilenceDetector:
    def __init__(self, ffmpeg_path: Path):
        self.ffmpeg_path = ffmpeg_path
        self._process: Optional[subprocess.Popen] = None
        self._is_cancelled: bool = False

    def detect(
        self,
        input_path: str,
        settings: SilenceSettings,
        video_duration: float,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> List[SilenceInterval]:
        self._is_cancelled = False

        af_filter = f"silencedetect=noise={settings.threshold_db}dB:d={settings.min_duration}"
        cmd = [
            str(self.ffmpeg_path),
            "-y",
            "-i", input_path,
            "-af", af_filter,
            "-f", "null",
            "-"
        ]

        logger.info(f"Running silence detection command: {' '.join(cmd)}")

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            start_new_session=True
        )

        stderr_lines: List[str] = []

        try:
            while True:
                if self._is_cancelled:
                    kill_process_group(self._process)
                    raise RuntimeError("無音検出処理がキャンセルされました。")

                line = self._process.stderr.readline()
                if not line and self._process.poll() is not None:
                    break

                if line:
                    stderr_lines.append(line)
                    # Attempt to parse time from stderr for progress
                    if "time=" in line and progress_callback and video_duration > 0:
                        try:
                            # e.g., time=00:01:23.45
                            parts = line.split("time=")[1].split()[0]
                            from ..utils.time_utils import hms_to_seconds
                            curr = hms_to_seconds(parts)
                            pct = min(100.0, (curr / video_duration) * 100.0)
                            progress_callback(pct, f"無音区間を解析中 ({pct:.1f}%)")
                        except Exception:
                            pass

            self._process.wait()
            if self._process.returncode != 0 and not self._is_cancelled:
                logger.warning(f"FFmpeg silencedetect exited with code {self._process.returncode}")

        finally:
            self._process = None

        full_stderr = "".join(stderr_lines)
        return SilenceParser.parse_log(full_stderr, total_duration=video_duration)

    def cancel(self) -> None:
        self._is_cancelled = True
        if self._process:
            kill_process_group(self._process)
