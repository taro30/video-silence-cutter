from dataclasses import dataclass, field
from typing import List, Tuple

@dataclass
class SilenceSettings:
    enabled: bool = True
    threshold_db: float = -30.0
    min_duration: float = 3.0
    padding: float = 0.2
    range_start: float = 0.0
    range_end: float = 0.0  # 0.0 means end of video
    # 手動で削除指定した区間 [(start_sec, end_sec), ...]。
    # 書き出し時にまとめて適用されるため、指定するたびにファイルを作る必要がない。
    manual_cuts: List[Tuple[float, float]] = field(default_factory=list)
