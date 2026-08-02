import os
import time
import subprocess
import threading
import logging
from pathlib import Path
from typing import Callable, List, Optional
from ..models.output_settings import OutputSettings
from ..utils.process_utils import kill_process_group

logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self, ffmpeg_path: Path):
        self.ffmpeg_path = ffmpeg_path
        self._process: Optional[subprocess.Popen] = None
        self._is_cancelled: bool = False

    def process_concat_demuxer(
        self,
        concat_list_path: Path,
        output_path: str,
        expected_duration: float = 0.0,
        progress_callback: Optional[Callable[[float, str, float, float], None]] = None
    ) -> bool:
        """
        FFmpeg の concat demuxer を使って無再エンコード (-c copy) で高速結合する。
        処理時間は数秒で完了し、画質劣化も一切発生しない。
        """
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
            "-loglevel", "warning",
            "-progress", "pipe:1",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list_path.resolve()),
            "-c", "copy",
            "-movflags", "+faststart",
            str(temp_out_file)
        ]

        logger.info(f"Executing Stream Copy Concat: {' '.join(cmd)}")

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            start_new_session=True
        )

        stderr_lines: List[str] = []

        def _read_stderr():
            try:
                for s_line in self._process.stderr:
                    if s_line:
                        stderr_lines.append(s_line)
            except Exception:
                pass

        t_err = threading.Thread(target=_read_stderr, daemon=True)
        t_err.start()

        curr_speed = ""
        try:
            while True:
                if self._is_cancelled:
                    kill_process_group(self._process)
                    if temp_out_file.exists():
                        try:
                            temp_out_file.unlink()
                        except Exception:
                            pass
                    raise RuntimeError("高速カット結合処理がキャンセルされました。")

                line = self._process.stdout.readline()
                if not line and self._process.poll() is not None:
                    break

                if line:
                    line_str = line.strip()
                    if line_str.startswith("speed="):
                        curr_speed = line_str.split("=")[1].strip()
                    elif line_str.startswith("out_time_us=") and progress_callback and expected_duration > 0:
                        try:
                            us = float(line_str.split("=")[1])
                            curr_sec = us / 1000000.0
                            pct = min(99.0, (curr_sec / expected_duration) * 100.0)
                            elapsed = time.time() - start_time
                            eta = (elapsed / (pct / 100.0)) - elapsed if pct > 0 else 0.0
                            speed_info = f" ({curr_speed})" if curr_speed else ""
                            progress_callback(pct, f"高速カット結合中 ({pct:.1f}%{speed_info})", elapsed, max(0.0, eta))
                        except Exception:
                            pass

            self._process.wait()
            t_err.join(timeout=3.0)

            if self._is_cancelled:
                if temp_out_file.exists():
                    temp_out_file.unlink()
                return False

            if self._process.returncode != 0:
                full_stderr = "".join(stderr_lines)
                logger.error(f"Stream Copy Concat failed:\n{full_stderr}")
                if temp_out_file.exists():
                    temp_out_file.unlink()
                raise RuntimeError(f"高速結合エラー:\n{full_stderr[-300:]}")

            if temp_out_file.exists():
                temp_out_file.replace(out_file)
                logger.info(f"Stream Copy Concat completed successfully -> {out_file}")
                return True
            else:
                raise RuntimeError("出力一時ファイルが見つかりません。")

        finally:
            self._process = None

    def process_single_trim_stream_copy(
        self,
        input_path: str,
        output_path: str,
        start_sec: float,
        end_sec: float,
        progress_callback: Optional[Callable[[float, str, float, float], None]] = None
    ) -> bool:
        """
        単一のトリミング区間を無再エンコード Stream Copy (-c copy) で超高速切り出しする。
        処理時間はわずか 0.5秒〜2秒で完了する。
        """
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
            "-loglevel", "warning",
            "-ss", f"{max(0.0, start_sec):.3f}",
        ]

        if end_sec > start_sec:
            cmd.extend(["-to", f"{end_sec:.3f}"])

        cmd.extend([
            "-i", input_path,
            "-c", "copy",
            "-movflags", "+faststart",
            str(temp_out_file)
        ])

        logger.info(f"Executing Ultra-Fast Stream Copy Trim: {' '.join(cmd)}")

        if progress_callback:
            progress_callback(50.0, "超高速 Stream Copy で動画を切り出し中...", 0.1, 0.0)

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            start_new_session=True
        )

        stderr_lines: List[str] = []
        def _read_stderr():
            try:
                for s_line in self._process.stderr:
                    if s_line:
                        stderr_lines.append(s_line)
            except Exception:
                pass

        t_err = threading.Thread(target=_read_stderr, daemon=True)
        t_err.start()

        try:
            self._process.wait()
            if self._process.returncode != 0:
                full_err = "".join(stderr_lines)
                logger.error(f"Stream Copy Trim failed: {full_err}")
                if temp_out_file.exists():
                    temp_out_file.unlink()
                raise RuntimeError(f"超高速トリミング切断エラー:\n{full_err[-300:]}")

            if temp_out_file.exists():
                temp_out_file.replace(out_file)
                logger.info(f"Stream Copy Trim completed -> {out_file}")
                if progress_callback:
                    progress_callback(100.0, "超高速トリミング完了！", time.time() - start_time, 0.0)
                return True
            else:
                raise RuntimeError("出力一時ファイルが見つかりません。")

        finally:
            self._process = None

    def process_video(
        self,
        input_path: str,
        output_path: str,
        filter_script_path: Path,
        v_label: str,
        a_label: str,
        settings: OutputSettings,
        expected_duration: float,
        progress_callback: Optional[Callable[[float, str, float, float], None]] = None,
        title_image_paths: Optional[List[Path]] = None
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

        # filter_complex の内容をファイルから読み込んで直接渡す
        # (FFmpeg 8.x で -filter_complex_script が deprecated かつ @file が未対応のため)
        filter_script_content = filter_script_path.read_text(encoding="utf-8")

        cmd = [
            str(self.ffmpeg_path),
            "-y",
            "-loglevel", "warning",
            "-progress", "pipe:1",
            "-threads", "0",
            "-i", input_path,
        ]

        # タイトル画像をオーバーレイ入力として追加（タイトルがある場合）
        if title_image_paths:
            for img_path in title_image_paths:
                cmd.extend(["-loop", "1", "-i", str(img_path)])

        cmd.extend([
            "-filter_complex", filter_script_content,
            "-map", f"[{v_label}]"
        ])

        if a_label:
            cmd.extend(["-map", f"[{a_label}]"])

        # Encoder options
        if settings.encoder == "h264_videotoolbox":
            cmd.extend([
                "-c:v", "h264_videotoolbox",
                "-b:v", settings.video_bitrate,
                "-r", "30",
                "-g", str(settings.gop),
                "-allow_sw", "1",          # ソフトウェアフォールバックを許可
                "-threads", "0",
            ])
        else:
            cmd.extend([
                "-c:v", "libx264",
                "-preset", "veryfast",     # 速度優先プリセット
                "-pix_fmt", settings.pix_fmt,
                "-b:v", settings.video_bitrate,
                "-maxrate", settings.max_bitrate,
                "-bufsize", settings.bufsize,
                "-r", "30",
                "-g", str(settings.gop),
                "-bf", str(settings.bframes),
                "-threads", "0",
            ])

        # タイトル画像を -loop 1 で入力している場合、動画が終わり次第停止させる
        if title_image_paths:
            cmd.append("-shortest")

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

        stderr_lines: List[str] = []

        # stderr を別スレッドで読み続けてパイプバッファのデッドロックを防ぐ
        def _read_stderr():
            try:
                for s_line in self._process.stderr:
                    if s_line:
                        stderr_lines.append(s_line)
            except Exception:
                pass

        t_err = threading.Thread(target=_read_stderr, daemon=True)
        t_err.start()

        curr_speed = ""
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

                if line:
                    line_str = line.strip()
                    if line_str.startswith("speed="):
                        curr_speed = line_str.split("=")[1].strip()
                    elif line_str.startswith("out_time_us=") and progress_callback and expected_duration > 0:
                        try:
                            us = float(line_str.split("=")[1])
                            curr_sec = us / 1000000.0
                            pct = min(99.0, (curr_sec / expected_duration) * 100.0)
                            elapsed = time.time() - start_time
                            eta = (elapsed / (pct / 100.0)) - elapsed if pct > 0 else 0.0
                            speed_info = f" ({curr_speed})" if curr_speed else ""
                            progress_callback(pct, f"動画を編集・エンコード中 ({pct:.1f}%{speed_info})", elapsed, max(0.0, eta))
                        except Exception:
                            pass

            self._process.wait()
            t_err.join(timeout=3.0)

            if self._is_cancelled:
                if temp_out_file.exists():
                    temp_out_file.unlink()
                return False

            if self._process.returncode != 0:
                full_stderr = "".join(stderr_lines)
                logger.error(f"FFmpeg encoding failed (exit {self._process.returncode}):\n{full_stderr}")

                # デバッグ用にログファイルへ完全な stderr を出力
                try:
                    import tempfile as _tf, datetime as _dt
                    log_dir = Path(_tf.gettempdir()) / "vsc_ffmpeg_logs"
                    log_dir.mkdir(exist_ok=True)
                    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
                    log_file = log_dir / f"ffmpeg_error_{ts}.log"
                    log_file.write_text(f"CMD:\n{' '.join(cmd)}\n\nSTDERR:\n{full_stderr}", encoding="utf-8")
                    logger.error(f"Full FFmpeg error log written to: {log_file}")
                except Exception:
                    pass

                if temp_out_file.exists():
                    temp_out_file.unlink()

                # バージョンヘッダーを除外（先頭スペースも考慮して strip() してから比較）
                skip_prefixes = (
                    "ffmpeg version", "built with", "(clang-",
                    "configuration:", "libav", "  lib", "Copyright",
                )
                clean_lines = [
                    l.strip() for l in full_stderr.splitlines()
                    if l.strip() and not any(l.strip().startswith(p) for p in skip_prefixes)
                ]
                err_msg = "\n".join(clean_lines[-10:]) if clean_lines else full_stderr[-400:]
                raise RuntimeError(f"FFmpegエンコードエラー:\n{err_msg}")

            # アトミックリネームで最終出力へ
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
