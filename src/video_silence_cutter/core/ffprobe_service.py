import json
import subprocess
import logging
from pathlib import Path
from typing import Optional
from ..models.video_info import VideoInfo

logger = logging.getLogger(__name__)

class FFprobeService:
    def __init__(self, ffprobe_path: Path):
        self.ffprobe_path = ffprobe_path

    def inspect_video(self, file_path: str) -> VideoInfo:
        p = Path(file_path)
        if not p.is_file():
            raise FileNotFoundError(f"動画ファイルが見つかりません: {file_path}")

        cmd = [
            str(self.ffprobe_path),
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(p)
        ]

        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        if res.returncode != 0:
            raise RuntimeError(f"動画情報を取得できませんでした: {res.stderr}")

        try:
            data = json.loads(res.stdout)
        except Exception as e:
            raise RuntimeError(f"ffprobeの応答解析に失敗しました: {e}")

        format_info = data.get("format", {})
        streams = data.get("streams", [])

        file_size = int(format_info.get("size", 0))
        duration = float(format_info.get("duration", 0.0))

        v_stream = None
        a_stream = None

        for s in streams:
            if s.get("codec_type") == "video" and not v_stream:
                v_stream = s
            elif s.get("codec_type") == "audio" and not a_stream:
                a_stream = s

        if not v_stream:
            raise ValueError("映像ストリームが見つかりません。")

        width = int(v_stream.get("width", 1280))
        height = int(v_stream.get("height", 720))
        video_codec = v_stream.get("codec_name", "unknown")
        pix_fmt = v_stream.get("pix_fmt", "yuv420p")
        video_bitrate = int(v_stream.get("bit_rate")) if v_stream.get("bit_rate") else None

        # Frame rate handling
        r_frame_rate = v_stream.get("r_frame_rate", "30/1")
        fps, fps_str = self._parse_frame_rate(r_frame_rate)

        # Aspect ratio
        display_aspect = v_stream.get("display_aspect_ratio")
        if not display_aspect or display_aspect == "0:1":
            display_aspect = f"{width}:{height}"

        # Audio stream info
        has_audio = a_stream is not None
        audio_codec = None
        audio_bitrate = None
        audio_channels = None
        sample_rate = None

        if has_audio:
            audio_codec = a_stream.get("codec_name")
            audio_bitrate = int(a_stream.get("bit_rate")) if a_stream.get("bit_rate") else None
            audio_channels = int(a_stream.get("channels")) if a_stream.get("channels") else None
            sample_rate = int(a_stream.get("sample_rate")) if a_stream.get("sample_rate") else None

        return VideoInfo(
            file_path=str(p.resolve()),
            file_name=p.name,
            file_size_bytes=file_size,
            duration_seconds=duration,
            width=width,
            height=height,
            aspect_ratio=display_aspect,
            fps=fps,
            fps_str=fps_str,
            video_codec=video_codec,
            video_bitrate=video_bitrate,
            pix_fmt=pix_fmt,
            audio_codec=audio_codec,
            audio_bitrate=audio_bitrate,
            audio_channels=audio_channels,
            sample_rate=sample_rate,
            has_audio=has_audio
        )

    def _parse_frame_rate(self, r_frame_rate: str) -> tuple[float, str]:
        try:
            if "/" in r_frame_rate:
                num, den = r_frame_rate.split("/")
                fps_val = float(num) / float(den)
                if num == "30000" and den == "1001":
                    return 29.97, "29.97 (30000/1001)"
                elif num == "24000" and den == "1001":
                    return 23.976, "23.98 (24000/1001)"
                elif num == "60000" and den == "1001":
                    return 59.94, "59.94 (60000/1001)"
                return round(fps_val, 2), f"{round(fps_val, 2)} ({r_frame_rate})"
            else:
                fps_val = float(r_frame_rate)
                return round(fps_val, 2), f"{round(fps_val, 2)}"
        except Exception:
            return 30.0, "30"
