import time
import logging
from pathlib import Path
from typing import Callable, Optional, List

from ..core.ffmpeg_locator import FFmpegLocator
from ..core.ffprobe_service import FFprobeService
from ..core.silence_detector import SilenceDetector
from ..core.interval_calculator import IntervalCalculator
from ..core.filter_builder import FilterBuilder
from ..core.video_processor import VideoProcessor
from ..core.output_validator import OutputValidator
from ..models.keep_interval import KeepInterval
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
        # 「無音区間を解析」はユーザーが明示的に実行する調査用の操作なので、
        # silence_settings.enabled（＝書き出し時に無音カットを適用するか）では
        # 抑止しない。ここで抑止すると、カット後にチェックが外れている状態では
        # 何度解析しても必ず「無音 0 件」になってしまう。
        self._reset_cancel()
        v_info = self.ffprobe_service.inspect_video(input_path)
        silences = []
        if v_info.has_audio:
            silences = self.silence_detector.detect(
                input_path, silence_settings, v_info.duration_seconds, progress_cb
            )
        else:
            logger.warning(f"音声ストリームが無いため無音解析をスキップしました: {input_path}")

        keeps = IntervalCalculator.calculate_keep_intervals(
            video_duration=v_info.duration_seconds,
            silence_intervals=silences,
            padding=silence_settings.padding,
            range_start=silence_settings.range_start,
            range_end=silence_settings.range_end,
            manual_cuts=silence_settings.manual_cuts
        )
        return v_info, silences, keeps

    def execute_full_pipeline(
        self,
        input_path: str,
        output_path: str,
        silence_settings: SilenceSettings,
        title_settings: TitleSettingsGroup,
        output_settings: OutputSettings,
        progress_cb: Optional[Callable[[float, str, float, float], None]] = None,
        cut_only: bool = False
    ) -> ProcessResult:
        """
        cut_only=True の場合は「カットのみ」モード。
        タイトル合成もスケーリングも行わず、必ず無再エンコード (-c copy) で
        切り出し・結合するだけなので、元の画質・解像度・コーデックがそのまま残る。
        """
        self._reset_cancel()
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
            range_end=silence_settings.range_end,
            manual_cuts=silence_settings.manual_cuts
        )

        # Stream Copy はキーフレームからしか切り出せないため、そのままだと削除区間の
        # 末尾（直前のキーフレーム〜削除終了点）が出力に残ってしまう。
        # 各保持区間の開始をキーフレーム位置まで前進させ、削除範囲を完全に消す。
        keeps = self._snap_keeps_to_keyframes(input_path, keeps)

        expected_output_duration = sum(k.duration for k in keeps)

        # カットのみモードではタイトル合成を一切行わない
        if cut_only:
            title_settings = None

        # 有効なタイトル合成があるか判定
        has_active_title = False
        if title_settings:
            for t_setting in [title_settings.title1, title_settings.title2, title_settings.title3]:
                if t_setting.enabled and t_setting.text.strip():
                    has_active_title = True
                    break

        # ── ⚡ 超高速トリミング分岐 (タイトル合成なし & 単一トリム切り出し) ──
        # 再エンコードが一切不要なため 1秒以内で爆速切り出し完了
        if not has_active_title and len(keeps) == 1:
            k = keeps[0]
            logger.info(f"⚡ 超高速 Stream Copy モードを適用します: {k.start:.2f}s -> {k.end:.2f}s")
            self.video_processor.process_single_trim_stream_copy(
                input_path=input_path,
                output_path=output_path,
                start_sec=k.start,
                end_sec=k.end,
                progress_callback=progress_cb
            )

            if progress_cb:
                progress_cb(95.0, "出力動画を検証中...", time.time() - start_time, 0.0)

            # Stream Copy 出力は入力の解像度・コーデックをそのまま引き継ぐため
            # 1280x720 / H.264 前提のチェックは行わない
            valid, val_msg, out_info = self.output_validator.validate(
                output_path,
                expected_output_duration,
                expected_width=0,
                expected_height=0,
                check_video_codec=False
            )
            if not valid:
                logger.warning(f"出力検証の警告: {val_msg}")

            total_elapsed = time.time() - start_time
            reduced_sec = max(0.0, v_info.duration_seconds - expected_output_duration)
            ratio = (1.0 - (expected_output_duration / v_info.duration_seconds)) if v_info.duration_seconds > 0 else 0.0

            return ProcessResult(
                success=True,
                input_file=input_path,
                output_file=output_path,
                original_duration=v_info.duration_seconds,
                processed_range_duration=v_info.duration_seconds,
                output_duration=expected_output_duration,
                reduced_seconds=reduced_sec,
                reduction_ratio=ratio,
                silence_count=len(silences),
                deleted_interval_count=len(silences),
                elapsed_seconds=total_elapsed,
                video_codec=out_info.video_codec if out_info else "unknown",
                audio_codec=(out_info.audio_codec or "なし") if out_info else "なし",
                width=out_info.width if out_info else 0,
                height=out_info.height if out_info else 0,
                fps=out_info.fps if out_info else 0.0,
                error_message=""
            )

        # カット指定が一切ない（動画全体をそのまま残す）かどうか。
        # 「先にカットだけ書き出し → その動画にタイトルだけ入れる」2パス運用では
        # ここが True になり、Stage 1 のセグメント切り出し・結合を丸ごと省略できる。
        no_cut_needed = (
            len(keeps) == 1
            and keeps[0].start <= 0.01
            and keeps[0].end >= v_info.duration_seconds - 0.05
        )

        temp_dir_obj = create_temp_dir()
        temp_dir = Path(temp_dir_obj.name)

        try:
            # ── Stage 2: 再エンコードが必要か判定 ──
            # タイトルなし & 解像度同じ → stream copy のまま出力（再エンコード不要）
            needs_encode = has_active_title or (
                not cut_only and (
                    v_info.width != output_settings.width or
                    v_info.height != output_settings.height
                )
            )

            if no_cut_needed and needs_encode:
                # ── Stage 1 スキップ: 入力から直接タイトル合成・エンコード ──
                logger.info("カット指定なし → Stage 1 (Stream Copy) を省略して直接エンコードします。")
                temp_concat_path = Path(input_path)
                actual_concat_duration = v_info.duration_seconds
            else:
                # ── Stage 1: Stream Copy でセグメント切り出し → Concat (超高速) ──
                logger.info("2ステージパイプライン: Stage 1 (Stream Copy) を開始します。")
                if progress_cb:
                    progress_cb(25.0, "セグメントを高速切り出し中...", time.time() - start_time, 0.0)

                def seg_cb(pct: float, msg: str, el: float, eta: float):
                    if progress_cb:
                        progress_cb(25.0 + (pct * 0.15), msg, el, eta)

                segment_files = self.video_processor.process_segments_to_files(
                    input_path=input_path,
                    keep_intervals=keeps,
                    temp_dir=temp_dir,
                    progress_callback=seg_cb
                )

                concat_list_path = temp_dir / "concat_list.txt"
                concat_list_path.write_text(
                    "\n".join(f"file '{seg.resolve()}'" for seg in segment_files),
                    encoding="utf-8"
                )

                temp_concat_path = temp_dir / "stage1_concat.mp4"

                def concat_cb(pct: float, msg: str, el: float, eta: float):
                    if progress_cb:
                        progress_cb(40.0 + (pct * 0.10), msg, el, eta)

                self.video_processor.process_concat_demuxer(
                    concat_list_path=concat_list_path,
                    output_path=str(temp_concat_path),
                    expected_duration=expected_output_duration,
                    progress_callback=concat_cb
                )

                # Stream copy はキーフレーム単位でカットするため実際の長さが expected と異なる場合がある
                # ffprobe で実尺を取得し Stage 2 のプログレス計算に使う
                try:
                    concat_info = self.ffprobe_service.inspect_video(str(temp_concat_path))
                    actual_concat_duration = concat_info.duration_seconds
                except Exception:
                    actual_concat_duration = expected_output_duration

            if needs_encode:
                logger.info("2ステージパイプライン: Stage 2 (エンコード) を開始します。")
                if progress_cb:
                    progress_cb(50.0, "エンコード中...", time.time() - start_time, 0.0)

                script_path, v_label, a_label, title_image_paths = FilterBuilder.build_overlay_only_filter_script(
                    has_audio=v_info.has_audio,
                    title_settings=title_settings,
                    temp_dir=temp_dir,
                    output_width=output_settings.width,
                    output_height=output_settings.height,
                )

                def enc_cb(pct: float, msg: str, el: float, eta: float):
                    if progress_cb:
                        progress_cb(50.0 + (pct * 0.42), msg, el, eta)

                self.video_processor.process_video(
                    input_path=str(temp_concat_path),
                    output_path=output_path,
                    filter_script_path=script_path,
                    v_label=v_label,
                    a_label=a_label,
                    settings=output_settings,
                    expected_duration=actual_concat_duration,
                    progress_callback=enc_cb,
                    title_image_paths=title_image_paths
                )
            else:
                reason = "カットのみモード" if cut_only else "解像度・タイトル変更なし"
                logger.info(f"{reason} → Stream Copy のまま出力（再エンコードスキップ）")
                if progress_cb:
                    progress_cb(85.0, "出力ファイルをコピー中...", time.time() - start_time, 0.0)
                import shutil
                if temp_concat_path == Path(input_path):
                    # Stage 1 を省略した場合 temp_concat_path は入力ファイル自身。
                    # move すると入力動画が消えてしまうためコピーする。
                    shutil.copy2(str(temp_concat_path), output_path)
                else:
                    shutil.move(str(temp_concat_path), output_path)

            if progress_cb:
                progress_cb(92.0, "出力ファイルを検証中...", time.time() - start_time, 0.0)

            # 再エンコードしていない場合は入力の解像度・コーデックのままなので検証条件を緩める
            valid, val_msg, out_info = self.output_validator.validate(
                output_path,
                expected_output_duration,
                expected_width=output_settings.width if needs_encode else 0,
                expected_height=output_settings.height if needs_encode else 0,
                check_video_codec=needs_encode
            )
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

    def _snap_keeps_to_keyframes(self, input_path: str, keeps: List[KeepInterval]) -> List[KeepInterval]:
        """
        各保持区間の開始位置を「その時刻以降の最初のキーフレーム」に合わせる。

        -c copy はキーフレームからしか切り出せず、指定より前のキーフレームから
        始まると削除したい区間の末尾が残ってしまう（「完全にカットされない」）。
        開始を後ろにずらすことで、削除範囲が必ず消えるようにする。

        ずらすと保持区間が消えてしまう場合（キーフレーム間隔より短い区間）は、
        映像を失わないよう元の開始位置のままにする。
        """
        if len(keeps) <= 1:
            return keeps

        snapped: List[KeepInterval] = []
        adjusted = 0

        for k in keeps:
            if k.start <= 0.01:
                snapped.append(k)
                continue

            kf = self.ffprobe_service.find_next_keyframe(input_path, k.start)
            if kf is None or kf <= k.start + 0.001:
                snapped.append(k)
                continue

            if kf >= k.end - 0.05:
                # ずらすと区間が消えてしまうので映像優先で元のまま残す
                logger.warning(
                    f"保持区間 {k.start:.2f}s〜{k.end:.2f}s はキーフレーム間隔より短いため "
                    f"位置調整をスキップします（削除区間の一部が残る可能性があります）。"
                )
                snapped.append(k)
                continue

            logger.info(f"キーフレームに合わせて開始位置を調整: {k.start:.2f}s → {kf:.2f}s")
            snapped.append(KeepInterval(start=kf, end=k.end))
            adjusted += 1

        if adjusted:
            logger.info(f"{adjusted} 箇所の開始位置をキーフレームに合わせました（削除漏れ防止）。")

        return snapped

    def _reset_cancel(self):
        """
        処理開始時にキャンセル状態を解除する。

        ProcessService（と配下の SilenceDetector / VideoProcessor）はアプリ起動中
        使い回されるため、これがないと一度キャンセルした以降のすべての実行が
        「処理がキャンセルされました。」で即座に失敗する。
        """
        self.silence_detector.reset_cancel()
        self.video_processor.reset_cancel()

    def cancel(self):
        self.silence_detector.cancel()
        self.video_processor.cancel()
