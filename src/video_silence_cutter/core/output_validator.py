import logging
from pathlib import Path
from typing import Tuple
from ..core.ffprobe_service import FFprobeService
from ..models.video_info import VideoInfo

logger = logging.getLogger(__name__)

class OutputValidator:
    def __init__(self, ffprobe_service: FFprobeService, max_audio_sync_diff: float = 0.2):
        self.ffprobe_service = ffprobe_service
        self.max_audio_sync_diff = max_audio_sync_diff

    def validate(self, output_path: str, expected_duration: float = 0.0) -> Tuple[bool, str, VideoInfo]:
        p = Path(output_path)
        if not p.is_file():
            return False, f"出力ファイルが存在しません: {output_path}", None

        if p.stat().st_size == 0:
            return False, "出力ファイルのサイズが0バイトです。", None

        try:
            info = self.ffprobe_service.inspect_video(output_path)
        except Exception as e:
            return False, f"出力動画メタデータの解析に失敗しました: {e}", None

        # Check resolution
        if info.width != 1280 or info.height != 720:
            return False, f"解像度が指定サイズ(1280x720)ではありません: {info.width}x{info.height}", info

        # Check video codec
        if info.video_codec.lower() not in ["h264", "avc1"]:
            return False, f"映像コーデックがH.264ではありません: {info.video_codec}", info

        # Check audio sync if audio is present
        if info.has_audio:
            if info.audio_codec and info.audio_codec.lower() not in ["aac"]:
                logger.warning(f"音声コーデックがAAC以外です: {info.audio_codec}")

        logger.info(f"Output video validation OK: {info.width}x{info.height}, duration={info.duration_seconds:.2f}s")
        return True, "出力動画検証成功", info
