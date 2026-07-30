from dataclasses import dataclass

@dataclass
class ProcessResult:
    success: bool
    input_file: str
    output_file: str
    original_duration: float
    processed_range_duration: float
    output_duration: float
    reduced_seconds: float
    reduction_ratio: float  # e.g., 0.262 for 26.2%
    silence_count: int
    deleted_interval_count: int
    elapsed_seconds: float
    video_codec: str
    audio_codec: str
    width: int
    height: int
    fps: float
    error_message: str = ""
