"""
FilterBuilder: FFmpeg filter_complex スクリプトを生成する。

タイトル合成は drawtext（libfreetype が必要）ではなく、
Pillow で生成した透過PNG画像を overlay フィルターで重ねる方式を使用する。
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

        # Title overlay via Pillow PNG images
        # 入力インデックスは [0] が元動画、[1]以降がタイトル画像
        overlay_input_idx = 1

        if title_settings:
            titles = [title_settings.title1, title_settings.title2, title_settings.title3]
            for idx, t_setting in enumerate(titles, start=1):
                if not t_setting.enabled or not t_setting.text.strip():
                    continue

                img_path = temp_dir / f"title_{idx}.png"
                rendered = TitleRenderer.render_title_image(
                    t_setting, img_path, output_width, output_height
                )
                if rendered is None:
                    continue

                title_image_paths.append(img_path)
                next_v = f"vtitle{idx}"

                # enable パラメータで表示時間を制御
                enable_expr = ""
                if t_setting.start_time >= 0 and t_setting.end_time > t_setting.start_time:
                    enable_expr = f":enable='between(t,{t_setting.start_time},{t_setting.end_time})'"

                lines.append(
                    f"[{current_v}][{overlay_input_idx}:v]overlay=0:0{enable_expr}[{next_v}];"
                )
                current_v = next_v
                overlay_input_idx += 1

        # 末尾のセミコロンを除去
        if lines and lines[-1].endswith(";"):
            lines[-1] = lines[-1][:-1]

        script_content = "\n".join(lines)
        temp_dir.mkdir(parents=True, exist_ok=True)
        script_path = temp_dir / "filter_complex_script.txt"
        script_path.write_text(script_content, encoding="utf-8")

        return script_path, current_v, a_concat_out, title_image_paths
