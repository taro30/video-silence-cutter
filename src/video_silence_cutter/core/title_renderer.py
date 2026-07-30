import os
from pathlib import Path
from typing import List, Optional
from ..models.title_settings import SingleTitleSettings, TitleSettingsGroup
from ..services.font_service import FontService

class TitleRenderer:
    @staticmethod
    def build_drawtext_filter(
        title_setting: SingleTitleSettings,
        text_file_path: Path,
        video_width: int = 1280,
        video_height: int = 720
    ) -> Optional[str]:
        if not title_setting.enabled or not title_setting.text.strip():
            return None

        # Resolve font file path
        font_path = title_setting.font_path
        if not font_path or not Path(font_path).is_file():
            resolved = FontService.find_font_path(title_setting.font_family)
            if resolved:
                font_path = resolved

        # Escape paths for ffmpeg drawtext filter
        # In filter_complex_script, backslash and colon and single quotes need escaping
        raw_textfile = str(text_file_path.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "'\\''")
        opts: List[str] = [
            f"textfile='{raw_textfile}'",
            "reload=1",
            f"fontsize={title_setting.font_size}",
            f"fontcolor={title_setting.font_color}",
        ]

        if font_path and Path(font_path).is_file():
            raw_fontfile = str(Path(font_path).resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "'\\''")
            opts.append(f"fontfile='{raw_fontfile}'")

        # X position
        align_h = title_setting.align_h
        if align_h == "左":
            opts.append("x=50")
        elif align_h == "右":
            opts.append("x=w-text_w-50")
        elif align_h == "中央":
            opts.append("x=(w-text_w)/2")
        else:  # カスタム
            opts.append(f"x={title_setting.x}")

        # Y position
        align_v = title_setting.align_v
        if align_v in ["上", "中央上部"]:
            opts.append("y=60")
        elif align_v in ["下", "中央下部"]:
            opts.append("y=h-text_h-60")
        elif align_v == "中央":
            opts.append("y=(h-text_h)/2")
        else:  # カスタム
            opts.append(f"y={title_setting.y}")

        # Border / Shadow
        if title_setting.border_width > 0:
            opts.append(f"borderw={title_setting.border_width}")
            opts.append(f"bordercolor={title_setting.border_color}")

        # Background Box
        if title_setting.bg_alpha > 0.0:
            opts.append("box=1")
            alpha_hex = int(title_setting.bg_alpha * 255)
            # Format hex boxcolor e.g. black@0.5 or hex
            opts.append(f"boxcolor={title_setting.bg_color}@{title_setting.bg_alpha:.2f}")

        # Time range enable='between(t,start,end)'
        if title_setting.start_time >= 0 and title_setting.end_time > title_setting.start_time:
            opts.append(f"enable='between(t,{title_setting.start_time},{title_setting.end_time})'")

        return "drawtext=" + ":".join(opts)

    @staticmethod
    def write_title_text_file(text: str, target_dir: Path, index: int) -> Path:
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / f"title_{index}.txt"
        file_path.write_text(text, encoding="utf-8")
        return file_path
