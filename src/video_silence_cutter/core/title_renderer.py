"""
TitleRenderer: タイトルテキストを Pillow で PNG 画像として生成し、
FFmpeg overlay フィルターで動画に合成する。
（drawtext フィルターは libfreetype が必要で Homebrew FFmpeg では利用不可のため使わない）
"""
import logging
from pathlib import Path
from typing import Optional, Tuple

from ..models.title_settings import SingleTitleSettings
from ..services.font_service import FontService

logger = logging.getLogger(__name__)


class TitleRenderer:
    """
    Pillowを使ってタイトルをPNG画像として生成し、
    FFmpeg overlay フィルター文字列を返す。
    """

    @staticmethod
    def render_title_image(
        title_setting: SingleTitleSettings,
        output_path: Path,
        video_width: int = 1280,
        video_height: int = 720,
    ) -> Optional[Path]:
        """
        タイトルテキストを透過PNG画像として生成する。
        フォントはシステムフォントから解決する。
        Returns: 生成されたPNGパス、または失敗時 None
        """
        if not title_setting.enabled or not title_setting.text.strip():
            return None

        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            logger.error("Pillow (PIL) が見つかりません。pip install Pillow を実行してください。")
            return None

        # フォントの解決
        font_size = title_setting.font_size
        font_path = title_setting.font_path
        if not font_path or not Path(font_path).is_file():
            font_path = FontService.find_font_path(title_setting.font_family)

        try:
            if font_path and Path(font_path).is_file():
                pil_font = ImageFont.truetype(str(font_path), font_size)
            else:
                # システムデフォルトフォント（フォールバック）
                fallback_fonts = [
                    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
                    "/System/Library/Fonts/Hiragino Sans GB.ttc",
                    "/System/Library/Fonts/Supplemental/Arial.ttf",
                    "/Library/Fonts/Arial.ttf",
                ]
                pil_font = None
                for f in fallback_fonts:
                    if Path(f).is_file():
                        pil_font = ImageFont.truetype(f, font_size)
                        break
                if pil_font is None:
                    pil_font = ImageFont.load_default()
        except Exception as e:
            logger.warning(f"Font load failed ({e}), using default")
            pil_font = ImageFont.load_default()

        text = title_setting.text.strip()

        # テキストのサイズ計算
        dummy_img = Image.new("RGBA", (1, 1))
        dummy_draw = ImageDraw.Draw(dummy_img)
        bbox = dummy_draw.textbbox((0, 0), text, font=pil_font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        padding = max(title_setting.border_width * 2, 4)

        # キャンバスサイズ（動画と同じサイズで透過PNG）
        img = Image.new("RGBA", (video_width, video_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # X位置計算
        align_h = title_setting.align_h
        if align_h == "左":
            x = 50
        elif align_h == "右":
            x = video_width - text_w - 50
        elif align_h == "中央":
            x = (video_width - text_w) // 2
        else:  # カスタム
            x = title_setting.x

        # Y位置計算
        align_v = title_setting.align_v
        if align_v in ["上", "中央上部"]:
            y = 60
        elif align_v in ["下", "中央下部"]:
            y = video_height - text_h - 60
        elif align_v == "中央":
            y = (video_height - text_h) // 2
        else:  # カスタム
            y = title_setting.y

        # 背景ボックス描画
        if title_setting.bg_alpha > 0.0:
            bg_color = _hex_to_rgba(title_setting.bg_color, title_setting.bg_alpha)
            draw.rectangle(
                [x - padding, y - padding, x + text_w + padding, y + text_h + padding],
                fill=bg_color
            )

        # 縁取り（ストローク）描画
        bw = title_setting.border_width
        if bw > 0:
            border_color = _hex_to_rgba(title_setting.border_color, 1.0)
            for dx in range(-bw, bw + 1):
                for dy in range(-bw, bw + 1):
                    if dx != 0 or dy != 0:
                        draw.text((x + dx, y + dy), text, font=pil_font, fill=border_color)

        # メインテキスト描画
        font_color = _hex_to_rgba(title_setting.font_color, 1.0)
        draw.text((x, y), text, font=pil_font, fill=font_color)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(output_path), "PNG")
        logger.debug(f"Title image generated: {output_path}")
        return output_path

    @staticmethod
    def build_overlay_filter(
        title_setting: SingleTitleSettings,
        title_image_path: Path,
        input_idx: int,
        video_width: int = 1280,
        video_height: int = 720,
    ) -> str:
        """
        FFmpeg overlay フィルター文字列を生成する。
        title_image_path は動画と同じサイズの透過PNG。
        enable パラメータで表示時間を制御。
        """
        enable = ""
        if title_setting.start_time >= 0 and title_setting.end_time > title_setting.start_time:
            enable = f":enable='between(t,{title_setting.start_time},{title_setting.end_time})'"

        # overlay=0:0 で左上原点に重ねる（画像自体が正しい位置に描画済み）
        return f"overlay=0:0{enable}"

    @staticmethod
    def write_title_text_file(text: str, target_dir: Path, index: int) -> Path:
        """後方互換性のために残す（drawtext 時代のメソッド）"""
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / f"title_{index}.txt"
        file_path.write_text(text, encoding="utf-8")
        return file_path


def _hex_to_rgba(hex_color: str, alpha: float) -> Tuple[int, int, int, int]:
    """#RRGGBB または #RRGGBBAA を (R, G, B, A) に変換する"""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 6:
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    elif len(hex_color) == 8:
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    else:
        r, g, b = 255, 255, 255
    a = int(max(0.0, min(1.0, alpha)) * 255)
    return (r, g, b, a)
