"""
FilterBuilder: FFmpeg filter_complex スクリプトを生成する。

タイトル合成は drawtext（libfreetype が必要）ではなく、
Pillow で生成した透過PNG画像を overlay フィルターで重ねる方式を使用する。
パフォーマンス最適化: 複数タイトルは1枚の合成PNGに事前合成し、
FFmpeg の overlay 操作を最小化する。
"""
from pathlib import Path
from typing import List, Optional, Tuple

from ..models.keep_interval import KeepInterval
from ..models.title_settings import TitleSettingsGroup
from .title_renderer import TitleRenderer


class FilterBuilder:
    @staticmethod
    def build_filter_script(
        keep_intervals: List[KeepInterval],
        has_audio: bool,
        title_settings: Optional[TitleSettingsGroup],
        temp_dir: Path,
        output_width: int = 1280,
        output_height: int = 720,
        fps_fraction: str = "30000/1001"
    ) -> Tuple[Path, str, str, List[Path]]:
        """
        filter_complex スクリプトファイルを生成する。

        Returns:
            (script_file_path, video_out_label, audio_out_label_or_empty, title_image_paths)

        title_image_paths は overlay 用に追加の -i オプションで渡す必要があるファイルリスト。
        パフォーマンス最適化: 全タイトルを1枚のPNGに合成済みのため最大1ファイル。
        """
        lines: List[str] = []
        title_image_paths: List[Path] = []

        if not keep_intervals:
            keep_intervals = [KeepInterval(0.0, 0.0)]

        num_intervals = len(keep_intervals)
        v_labels: List[str] = []
        a_labels: List[str] = []

        for i, interval in enumerate(keep_intervals):
            v_label = f"v{i}"
            a_label = f"a{i}"
            v_labels.append(f"[{v_label}]")
            a_labels.append(f"[{a_label}]")

            # Trim options
            trim_opts = []
            if interval.start > 0:
                trim_opts.append(f"start={interval.start:.4f}")
            if interval.end > 0:
                trim_opts.append(f"end={interval.end:.4f}")

            trim_filter = f"trim={':'.join(trim_opts)}," if trim_opts else ""
            atrim_filter = f"atrim={':'.join(trim_opts)}," if trim_opts else ""

            lines.append(f"[0:v]{trim_filter}setpts=PTS-STARTPTS[{v_label}];")
            if has_audio:
                lines.append(f"[0:a]{atrim_filter}asetpts=PTS-STARTPTS[{a_label}];")

        # Concat step
        v_concat_out = "vconcat"
        a_concat_out = "aconcat" if has_audio else ""

        if has_audio:
            concat_inputs = "".join([f"{v_labels[i]}{a_labels[i]}" for i in range(num_intervals)])
            lines.append(f"{concat_inputs}concat=n={num_intervals}:v=1:a=1[{v_concat_out}][{a_concat_out}];")
        else:
            concat_inputs = "".join(v_labels)
            lines.append(f"{concat_inputs}concat=n={num_intervals}:v=1:a=0[{v_concat_out}];")

        # Scale + Pad + SAR + FPS + Format
        scaled_out = "vscaled"
        lines.append(
            f"[{v_concat_out}]scale={output_width}:{output_height}:force_original_aspect_ratio=decrease,"
            f"pad={output_width}:{output_height}:(ow-iw)/2:(oh-ih)/2:black,"
            f"setsar=1,fps=30,format=yuv420p[{scaled_out}];"
        )

        current_v = scaled_out

        # ── パフォーマンス最適化: 全タイトルを1枚の合成PNGに事前合成 ──
        # 複数の overlay 操作を1回にまとめることで大幅な速度改善
        if title_settings:
            titles = [title_settings.title1, title_settings.title2, title_settings.title3]
            active_titles = [t for t in titles if t.enabled and t.text.strip()]

            if active_titles:
                # 合成PNG（全タイトルを1枚に重ね描き）
                composite_img_path = temp_dir / "title_composite.png"
                rendered = TitleRenderer.render_composite_title_image(
                    title_settings_list=active_titles,
                    output_path=composite_img_path,
                    video_width=output_width,
                    video_height=output_height,
                )
                if rendered:
                    title_image_paths.append(composite_img_path)

                    # enable: 最初のタイトルの時間範囲を使用（複合画像のため）
                    first = active_titles[0]
                    enable_expr = ""
                    if first.start_time >= 0 and first.end_time > first.start_time:
                        enable_expr = f":enable='between(t,{first.start_time},{first.end_time})'"

                    next_v = "vtitle_composite"
                    lines.append(
                        f"[{current_v}][1:v]overlay=0:0{enable_expr}[{next_v}];"
                    )
                    current_v = next_v

        # 末尾のセミコロンを除去
        if lines and lines[-1].endswith(";"):
            lines[-1] = lines[-1][:-1]

        script_content = "\n".join(lines)
        temp_dir.mkdir(parents=True, exist_ok=True)
        script_path = temp_dir / "filter_complex_script.txt"
        script_path.write_text(script_content, encoding="utf-8")

        return script_path, current_v, a_concat_out, title_image_paths
