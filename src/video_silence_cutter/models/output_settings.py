from dataclasses import dataclass

@dataclass
class OutputSettings:
    output_dir: str = ""
    output_filename: str = ""
    encoder: str = "libx264"  # libx264 or h264_videotoolbox
    width: int = 1280
    height: int = 720
    fps_str: str = "30000/1001"
    video_bitrate: str = "1500k"
    max_bitrate: str = "1500k"
    bufsize: str = "3000k"
    gop: int = 60
    bframes: int = 2
    pix_fmt: str = "yuv420p"
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    audio_channels: int = 2
    sample_rate: int = 48000
    faststart: bool = True
