from dataclasses import dataclass

@dataclass
class OutputSettings:
    output_dir: str = ""
    output_filename: str = ""
    encoder: str = "h264_videotoolbox"  # h264_videotoolbox (Apple Silicon) or libx264
    width: int = 1280
    height: int = 720
    fps_str: str = "30000/1001"
    video_bitrate: str = "8000k"
    max_bitrate: str = "10000k"
    bufsize: str = "16000k"
    gop: int = 60
    bframes: int = 0   # videotoolbox は B フレーム非対応
    pix_fmt: str = "yuv420p"
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    audio_channels: int = 2
    sample_rate: int = 48000
    faststart: bool = True
