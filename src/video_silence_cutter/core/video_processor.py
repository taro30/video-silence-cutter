import os
import time
import subprocess
import logging
from pathlib import Path
from typing import Callable, Optional
from ..models.output_settings import OutputSettings
from ..utils.process_utils import kill_process_group

logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self, ffmpeg_path: Path):
        self.ffmpeg_path = ffmpeg_path
        self._process: Optional[subprocess.Popen] = None
        self._is_cancelled: bool = False

    def process_video(
        self,
        input_path: str,
        output_path: str,
        filter_script_path: Path,
        v_label: str,
        a_label: str,
        settings: OutputSettings,
        expected_duration: float,
        progress_callback: Optional[Callable[[float, str, float, float], None]] = None
    ) -> bool:
        self._is_cancelled = False
        start_time = time.time()

        out_file = Path(output_path)
        temp_out_file = out_file.with_name(out_file.name + ".processing.mp4")

        if temp_out_file.exists():
            try:
                temp_out_file.unlink()
            except Exception:
                pass

        cmd = [
            str(self.ffmpeg_path),
            "-y",
            "-progress", "pipe:1",
            "-i", input_path,
            "-filter_complex_script", str(filter_script_path.resolve()),
            "-map", f"[{v_label}]"
        ]

        if a_label:
            cmd.extend(["-map", f"[{a_label}]"])

        # Encoder options
        if settings.encoder == "h264_videotoolbox":
            cmd.extend(["-c:v", "h264_videotoolbox"])
        else:
            cmd.extend(["-c:v", "libx264"])

        cmd.extend([
            "-pix_fmt", settings.pix_fmt,
            "-b:v", settings.video_bitrate,
            "-maxrate", settings.max_bitrate,
            "-bufsize", settings.bufsize,
            "-g", str(settings.gop),
            "-bf", str(settings.bframes),
        ])

        if settings.faststart:
            cmd.extend(["-movflags", "+faststart"])

        if a_label:
            cmd.extend([
                "-c:a", settings.audio_codec,
                "-b:a", settings.audio_bitrate,
                "-ac", str(settings.audio_channels),
                "-ar", str(settings.sample_rate)
            ])

        cmd.append(str(temp_out_file))

        logger.info(f"Executing Video Processing: {' '.join(cmd)}")

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            start_new_session=True
        )

        try:
            while True:
                if self._is_cancelled:
                    kill_process_group(self._process)
                    if temp_out_file.exists():
                        try:
                            temp_out_file.unlink()
                        except Exception:
                            pass
                    raise RuntimeError("動画編集・エンコード処理がキャンセルされました。")

                line = self._process.stdout.readline()
                if not line and self._process.poll() is not None:
                    break

                if line and progress_callback and expected_duration > 0:
                    line_str = line.strip()
                    if line_str.startswith("out_time_us="):
                        try:
                            us = float(line_str.split("=")[1])
                            curr_sec = us / 1000000.0
                            pct = min(99.0, (curr_sec / expected_duration) * 100.0)
                            elapsed = time.time() - start_time
                            eta = (elapsed / (pct / 100.0)) - elapsed if pct > 0 else 0.0
                            progress_callback(pct, f"動画を編集・エンコード中 ({pct:.1f}%)", elapsed, max(0.0, eta))
                        except Exception:
                            pass

            self._process.wait()

            if self._is_cancelled:
                if temp_out_file.exists():
                    temp_out_file.unlink()
                return False

            if self._process.returncode != 0:
                stderr_err = self._process.stderr.read()
                logger.error(f"FFmpeg encoding failed with exit code {self._process.returncode}: {stderr_err}")
                if temp_out_file.exists():
                    temp_out_file.unlink()
                # Get meaningful tail error message
                err_tail = stderr_err.strip().splitlines()[-10:] if stderr_err else ["不明なFFmpegエラー"]
                err_msg = "\n".join(err_tail)
                raise RuntimeError(f"FFmpegエンコードエラー:\n{err_msg}")

            # Atomic rename to final output
            if temp_out_file.exists():
                temp_out_file.replace(out_file)
                logger.info(f"Encoding completed successfully -> {out_file}")
                return True
            else:
                raise RuntimeError("出力一時ファイルが見つかりません。")

        finally:
            self._process = None

    def cancel(self) -> None:
        self._is_cancelled = True
        if self._process:
            kill_process_group(self._process)
