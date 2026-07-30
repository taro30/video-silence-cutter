import re
from typing import List, Optional
from ..models.silence_interval import SilenceInterval

class SilenceParser:
    """
    Parses FFmpeg stderr output containing silencedetect logs:
      [silencedetect @ 0x...] silence_start: 10.5
      [silencedetect @ 0x...] silence_end: 15.2 | silence_duration: 4.7
    """
    RE_START = re.compile(r"silence_start:\s*(-?\d+(?:\.\d+)?)")
    RE_END = re.compile(r"silence_end:\s*(-?\d+(?:\.\d+)?)")

    @classmethod
    def parse_log(cls, log_text: str, total_duration: Optional[float] = None) -> List[SilenceInterval]:
        intervals: List[SilenceInterval] = []
        current_start: Optional[float] = None

        for line in log_text.splitlines():
            start_match = cls.RE_START.search(line)
            if start_match:
                # If there was a previous unclosed silence_start, close it at current start or handle
                val = float(start_match.group(1))
                current_start = max(0.0, val)
                continue

            end_match = cls.RE_END.search(line)
            if end_match:
                if current_start is not None:
                    end_val = float(end_match.group(1))
                    if total_duration is not None:
                        end_val = min(total_duration, end_val)
                    if end_val > current_start:
                        intervals.append(SilenceInterval(start=current_start, end=end_val))
                    current_start = None

        # If log ended with an open silence_start and we know total_duration
        if current_start is not None and total_duration is not None:
            if total_duration > current_start:
                intervals.append(SilenceInterval(start=current_start, end=total_duration))

        return intervals
