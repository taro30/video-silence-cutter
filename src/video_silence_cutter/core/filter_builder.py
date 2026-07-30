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
    ) -> Tuple[Path, str, str]:
        """
        Builds filter_complex_script file.
        Returns (script_file_path, video_out_label, audio_out_label_or_empty)
        """
        lines: List[str] = []

        if not keep_intervals:
            # Fallback: keep full video if intervals empty
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

            trim_str = ":" + ":".join(trim_opts) if trim_opts else ""

            # Video trim
            lines.append(f"[0:v]trim={trim_str},setpts=PTS-STARTPTS[{v_label}];")

            # Audio trim (if audio exists)
            if has_audio:
                lines.append(f"[0:a]atrim={trim_str},asetpts=PTS-STARTPTS[{a_label}];")

        # Concat step
        v_concat_out = "vconcat"
        a_concat_out = "aconcat" if has_audio else ""

        if has_audio:
            concat_inputs = "".join([f"{v_labels[i]}{a_labels[i]}" for i in range(num_intervals)])
            lines.append(f"{concat_inputs}concat=n={num_intervals}:v=1:a=1[{v_concat_out}][{a_concat_out}];")
        else:
            concat_inputs = "".join(v_labels)
            lines.append(f"{concat_inputs}concat=n={num_intervals}:v=1:a=0[{v_concat_out}];")

        # Scale, Pad, SAR, FPS, Format step
        scaled_out = "vscaled"
        scale_pad_chain = (
            f"[{v_concat_out}]scale={output_width}:{output_height}:force_original_aspect_ratio=decrease,"
            f"pad={output_width}:{output_height}:(ow-iw)/2:(oh-ih)/2:black,"
            f"setsar=1,fps={fps_fraction},format=yuv420p[{scaled_out}];"
        )
        lines.append(scale_pad_chain)

        current_v = scaled_out

        # Title drawtext filters
        if title_settings:
            titles = [title_settings.title1, title_settings.title2, title_settings.title3]
            for idx, t_setting in enumerate(titles, start=1):
                if t_setting.enabled and t_setting.text.strip():
                    txt_file = TitleRenderer.write_title_text_file(t_setting.text, temp_dir, idx)
                    dt_filter = TitleRenderer.build_drawtext_filter(
                        t_setting, txt_file, output_width, output_height
                    )
                    if dt_filter:
                        next_v = f"vtitle{idx}"
                        lines.append(f"[{current_v}]{dt_filter}[{next_v}];")
                        current_v = next_v

        # Final label cleanup: remove trailing semicolon from last filter line
        if lines and lines[-1].endswith(";"):
            lines[-1] = lines[-1][:-1]

        script_content = "\n".join(lines)
        temp_dir.mkdir(parents=True, exist_ok=True)
        script_path = temp_dir / "filter_complex_script.txt"
        script_path.write_text(script_content, encoding="utf-8")

        return script_path, current_v, a_concat_out
