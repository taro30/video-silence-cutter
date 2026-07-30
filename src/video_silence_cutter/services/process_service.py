import os
import time
import logging
import subprocess
from pathlib import Path
from typing import Callable, Optional, List

from ..core.ffmpeg_locator import FFmpegLocator
from ..core.ffprobe_service import FFprobeService
from ..core.silence_detector import SilenceDetector
from ..core.interval_calculator import IntervalCalculator
from ..core.filter_builder import FilterBuilder
from ..core.video_processor import VideoProcessor
from ..core.output_validator import OutputValidator
from ..models.silence_settings import SilenceSettings
from ..models.title_settings import TitleSettingsGroup
from ..models.output_settings import OutputSettings
from ..models.process_result import ProcessResult
from ..utils.path_utils import create_temp_dir

logger = logging.getLogger(__name__)

class ProcessService:
    def __init__(self, locator: FFmpegLocator):
        self.locator = locator
        self.ffmpeg_path = locator.find_ffmpeg()
        self.ffprobe_path = locator.find_ffprobe()

        if not self.ffmpeg_path or not self.ffprobe_path:
            raise RuntimeError("FFmpeg または ffprobe が見つかりません。")

        self.ffprobe_service = FFprobeService(self.ffprobe_path)
        self.silence_detector = SilenceDetector(self.ffmpeg_path)
        self.video_processor = VideoProcessor(self.ffmpeg_path)
        self.output_validator = OutputValidator(self.ffprobe_service)

    def analyze_silence_only(
        self,
        input_path: str,
        silence_settings: SilenceSettings,
        progress_cb: Optional[Callable[[float, str], None]] = None
    ):
        v_info = self.ffprobe_service.inspect_video(input_path)
        silences = []
        if silence_settings.enabled and v_info.has_audio:
            silences = self.silence_detector.detect(
                input_path, silence_settings, v_info.duration_seconds, progress_cb
            )

        keeps = IntervalCalculator.calculate_keep_intervals(
            video_duration=v_info.duration_seconds,
            silence_intervals=silences,
            padding=silence_settings.padding,
            range_start=silence_settings.range_start,
            range_end=silence_settings.range_end
        )
        return v_info, silences, keeps

    def execute_full_pipeline(
        self,
        input_path: str,
        output_path: str,
        silence_settings: SilenceSettings,
        title_settings: TitleSettingsGroup,
        output_settings: OutputSettings,
        progress_cb: Optional[Callable[[float, str, float, float], None]] = None
    ) -> ProcessResult:
        start_time = time.time()
        v_info = self.ffprobe_service.inspect_video(input_path)

        # Step 1: Detect silence
        if progress_cb:
            progress_cb(5.0, "音声を解析中...", 0.0, 0.0)

        silences = []
        if silence_settings.enabled and v_info.has_audio:
            def det_cb(pct: float, msg: str):
                if progress_cb:
                    scaled_pct = 5.0 + (pct * 0.20)  # 5% to 25%
                    progress_cb(scaled_pct, msg, time.time() - start_time, 0.0)

            silences = self.silence_detector.detect(
                input_path, silence_settings, v_info.duration_seconds, det_cb
            )

        # Step 2: Calculate keep intervals
        if progress_cb:
            progress_cb(25.0, "無音区間を計算中...", time.time() - start_time, 0.0)

        range_end = silence_settings.range_end if silence_settings.range_end > 0 else v_info.duration_seconds
        processed_range_dur = max(0.0, range_end - max(0.0, silence_settings.range_start))

        keeps = IntervalCalculator.calculate_keep_intervals(
            video_duration=v_info.duration_seconds,
            silence_intervals=silences,
            padding=silence_settings.padding,
            range_start=silence_settings.range_start,
            range_end=silence_settings.range_end
        )

        expected_output_duration = sum(k.duration for k in keeps)

        # 有効なタイトル合成があるか判定
        has_active_title = False
        if title_settings:
            for t_setting in [title_settings.title1, title_settings.title2, title_settings.title3]:
                if t_setting.enabled and t_setting.text.strip():
                    has_active_title = True
                    break

        temp_dir_obj = create_temp_dir()
        temp_dir = Path(temp_dir_obj.name)

        try:
            def enc_cb(pct: float, msg: str, el: float, eta: float):
                if progress_cb:
                    scaled_pct = 30.0 + (pct * 0.60)  # 30% to 90%
                    progress_cb(scaled_pct, msg, el, eta)

            # ── ⚡ 【超高速パス】タイトルなしの場合、無再エンコード Stream Copy 結合（0.2秒〜数秒で完了） ──
            if not has_active_title:
                logger.info("タイトル合成なし: 無再エンコード Stream Copy パスを実行します。")
                if progress_cb:
                    progress_cb(30.0, "超高速カット結合中...", time.time() - start_time, 0.0)

                seg_paths: List[Path] = []
                for idx, interval in enumerate(keeps):
                    seg_path = temp_dir / f"seg_{idx:04d}.mp4"
                    cmd_cut = [
                        str(self.locator.find_ffmpeg()),
                        "-y", "-loglevel", "error",
                        "-ss", f"{interval.start:.4f}",
                    ]
                    if interval.end > 0:
                        cmd_cut.extend(["-to", f"{interval.end:.4f}"])

                    cmd_cut.extend([
                        "-i", input_path,
                        "-c", "copy",
                        "-avoid_negative_ts", "make_zero",
                        str(seg_path)
                    ])
                    subprocess.run(cmd_cut, check=True)
                    seg_paths.append(seg_path)

                # concat list ファイルの作成
                concat_list_file = temp_dir / "concat_list.txt"
                lines = [f"file '{p.resolve()}'" for p in seg_paths]
                concat_list_file.write_text("\n".join(lines), encoding="utf-8")

                # Concat Demuxer 結合実行
                self.video_processor.process_concat_demuxer(
                    concat_list_path=concat_list_file,
                    output_path=output_path,
                    expected_duration=expected_output_duration,
                    progress_callback=enc_cb
                )

            # ── 【タイトル合成あり】スマートハイブリッドパス（タイトル表示部のみエンコード、残りはStream Copy） ──
            else:
                # 有効なタイトルの最大終了時刻を算出
                max_title_end = 0.0
                if title_settings:
                    for t_setting in [title_settings.title1, title_settings.title2, title_settings.title3]:
                        if t_setting.enabled and t_setting.text.strip():
                            max_title_end = max(max_title_end, t_setting.end_time)

                logger.info(f"タイトル合成あり: 最大タイトル表示時刻 = {max_title_end:.2f}s")

                title_keeps = [k for k in keeps if k.start < max_title_end]
                copy_keeps = [k for k in keeps if k.start >= max_title_end]

                seg_paths: List[Path] = []

                # Part 1: タイトル表示範囲の区間（ここだけタイトル画像合成エンコード）
                if title_keeps:
                    logger.info(f"タイトル適用区間 ({len(title_keeps)}件) のエンコードを開始")
                    seg_title_out = temp_dir / "seg_title_encoded.mp4"

                    # タイトル区間のみのフィルター生成
                    script_path, v_label, a_label, title_image_paths = FilterBuilder.build_filter_script(
                        keep_intervals=title_keeps,
                        has_audio=v_info.has_audio,
                        title_settings=title_settings,
                        temp_dir=temp_dir,
                        output_width=output_settings.width,
                        output_height=output_settings.height,
                        fps_fraction=output_settings.fps_str
                    )

                    title_expected_dur = sum(k.duration for k in title_keeps)
                    self.video_processor.process_video(
                        input_path=input_path,
                        output_path=str(seg_title_out),
                        filter_script_path=script_path,
                        v_label=v_label,
                        a_label=a_label,
                        settings=output_settings,
                        expected_duration=title_expected_dur,
                        progress_callback=enc_cb,
                        title_image_paths=title_image_paths
                    )
                    seg_paths.append(seg_title_out)

                # Part 2: タイトル表示終了後の残り全区間（無再エンコード Stream Copy で即切断）
                if copy_keeps:
                    logger.info(f"タイトル終了後区間 ({len(copy_keeps)}件) の Stream Copy 抽出を開始")
                    for idx, interval in enumerate(copy_keeps):
                        seg_copy_path = temp_dir / f"seg_copy_{idx:04d}.mp4"
                        cmd_cut = [
                            str(self.locator.find_ffmpeg()),
                            "-y", "-loglevel", "error",
                            "-ss", f"{interval.start:.4f}",
                        ]
                        if interval.end > 0:
                            cmd_cut.extend(["-to", f"{interval.end:.4f}"])

                        cmd_cut.extend([
                            "-i", input_path,
                            "-c", "copy",
                            "-avoid_negative_ts", "make_zero",
                            str(seg_copy_path)
                        ])
                        subprocess.run(cmd_cut, check=True)
                        seg_paths.append(seg_copy_path)

                # 全セグメントを Concat Demuxer で一括結合
                concat_list_file = temp_dir / "concat_list.txt"
                lines = [f"file '{p.resolve()}'" for p in seg_paths]
                concat_list_file.write_text("\n".join(lines), encoding="utf-8")

                self.video_processor.process_concat_demuxer(
                    concat_list_path=concat_list_file,
                    output_path=output_path,
                    expected_duration=expected_output_duration,
                    progress_callback=enc_cb
                )

            # Step 5: Output validation
            if progress_cb:
                progress_cb(92.0, "出力ファイルを検証中...", time.time() - start_time, 0.0)

            valid, val_msg, out_info = self.output_validator.validate(output_path, expected_output_duration)
            if not valid:
                raise RuntimeError(f"出力検証失敗: {val_msg}")

            total_elapsed = time.time() - start_time
            reduced_sec = max(0.0, processed_range_dur - out_info.duration_seconds)
            ratio = (reduced_sec / processed_range_dur) if processed_range_dur > 0 else 0.0

            if progress_cb:
                progress_cb(100.0, "完了", total_elapsed, 0.0)

            return ProcessResult(
                success=True,
                input_file=input_path,
                output_file=output_path,
                original_duration=v_info.duration_seconds,
                processed_range_duration=processed_range_dur,
                output_duration=out_info.duration_seconds,
                reduced_seconds=reduced_sec,
                reduction_ratio=ratio,
                silence_count=len(silences),
                deleted_interval_count=len(silences),
                elapsed_seconds=total_elapsed,
                video_codec=out_info.video_codec,
                audio_codec=out_info.audio_codec or "なし",
                width=out_info.width,
                height=out_info.height,
                fps=out_info.fps
            )

        finally:
            temp_dir_obj.cleanup()

    def cancel(self):
        self.silence_detector.cancel()
        self.video_processor.cancel()
