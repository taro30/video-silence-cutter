from dataclasses import dataclass

@dataclass
class SilenceSettings:
    enabled: bool = True
    threshold_db: float = -30.0
    min_duration: float = 3.0
    padding: float = 0.2
    range_start: float = 0.0
    range_end: float = 0.0  # 0.0 means end of video
