from dataclasses import dataclass
from typing import Optional

@dataclass
class VideoInfo:
    file_path: str
    file_name: str
    file_size_bytes: int
    duration_seconds: float
    width: int
    height: int
    aspect_ratio: str
    fps: float
    fps_str: str
    video_codec: str
    video_bitrate: Optional[int] = None
    pix_fmt: Optional[str] = None
    audio_codec: Optional[str] = None
    audio_bitrate: Optional[int] = None
    audio_channels: Optional[int] = None
    sample_rate: Optional[int] = None
    has_audio: bool = True
