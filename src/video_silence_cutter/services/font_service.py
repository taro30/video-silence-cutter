import os
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class FontService:
    FONT_SEARCH_PATHS = [
        Path("/System/Library/Fonts"),
        Path("/System/Library/Fonts/Supplemental"),
        Path("/Library/Fonts"),
        Path.home() / "Library" / "Fonts",
    ]

    PREFERRED_FONTS = [
        "Hiragino Sans",
        "Hiragino Kaku Gothic ProN",
        "Hiragino Maru Gothic ProN",
        "Hiragino Mincho ProN",
        "Yu Gothic",
        "YuGothic",
        "Noto Sans CJK JP",
        "Noto Sans JP",
    ]

    @classmethod
    def find_font_path(cls, font_family: str) -> Optional[str]:
        # 1. Search matching font files in font directories
        font_files = cls.scan_available_font_files()

        # Direct match or partial match in scan
        for f_name, f_path in font_files.items():
            if font_family.lower() in f_name.lower():
                return str(f_path)

        # Fallback to preferred system fonts
        for pref in cls.PREFERRED_FONTS:
            for f_name, f_path in font_files.items():
                if pref.lower() in f_name.lower():
                    logger.info(f"Fallback font chosen: {f_name} -> {f_path}")
                    return str(f_path)

        # Fallback to any valid font file found
        if font_files:
            fallback = list(font_files.values())[0]
            return str(fallback)

        return None

    @classmethod
    def scan_available_font_files(cls) -> Dict[str, Path]:
        font_map: Dict[str, Path] = {}

        for search_dir in cls.FONT_SEARCH_PATHS:
            if not search_dir.exists():
                continue
            for ext in ["*.ttf", "*.otf", "*.ttc", "*.TTF", "*.OTF", "*.TTC"]:
                for font_file in search_dir.glob(ext):
                    name_key = font_file.stem
                    font_map[name_key] = font_file

        return font_map
