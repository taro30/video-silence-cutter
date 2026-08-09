from typing import List, Optional, Tuple
from ..models.silence_interval import SilenceInterval
from ..models.keep_interval import KeepInterval

class IntervalCalculator:
    @staticmethod
    def calculate_keep_intervals(
        video_duration: float,
        silence_intervals: List[SilenceInterval],
        padding: float = 0.2,
        range_start: float = 0.0,
        range_end: float = 0.0,
        manual_cuts: Optional[List[Tuple[float, float]]] = None,
    ) -> List[KeepInterval]:
        """
        manual_cuts は手動で「この範囲を削除」と指定した区間。
        無音区間と違い padding による短縮は行わず、指定どおりそのまま削除する。
        """
        if video_duration <= 0:
            return []

        # Validate range
        r_start = max(0.0, range_start)
        if range_end <= 0.0 or range_end > video_duration:
            r_end = video_duration
        else:
            r_end = range_end

        if r_start >= r_end:
            return []

        # 1. Collect cut (removal) intervals
        cut_intervals: List[tuple[float, float]] = []

        # Area before range_start is cut
        if r_start > 0.0:
            cut_intervals.append((0.0, r_start))

        # Area after range_end is cut
        if r_end < video_duration:
            cut_intervals.append((r_end, video_duration))

        # Process silence intervals with padding within [r_start, r_end]
        for silence in silence_intervals:
            # Clamp to range
            s = max(r_start, silence.start)
            e = min(r_end, silence.end)
            if s >= e:
                continue

            # Apply padding
            cut_s = s + padding
            cut_e = e - padding

            if cut_s < cut_e:
                cut_intervals.append((cut_s, cut_e))

        # Manual delete intervals (padding は適用しない)
        for m_start, m_end in (manual_cuts or []):
            s = max(r_start, min(m_start, m_end))
            e = min(r_end, max(m_start, m_end))
            if s < e:
                cut_intervals.append((s, e))

        # 2. Merge overlapping or adjacent cut intervals
        merged_cuts = IntervalCalculator.merge_cut_intervals(cut_intervals)

        # 3. Invert cut intervals to find KeepIntervals
        keep_intervals: List[KeepInterval] = []
        current_pos = 0.0

        for cut_s, cut_e in merged_cuts:
            if cut_s > current_pos:
                keep_intervals.append(KeepInterval(start=current_pos, end=cut_s))
            current_pos = max(current_pos, cut_e)

        if current_pos < video_duration:
            keep_intervals.append(KeepInterval(start=current_pos, end=video_duration))

        # Filter out 0 duration keep intervals
        valid_keeps = [k for k in keep_intervals if k.duration > 0.0001]
        return valid_keeps

    @staticmethod
    def merge_cut_intervals(intervals: List[tuple[float, float]]) -> List[tuple[float, float]]:
        if not intervals:
            return []

        # Sort by start time
        sorted_intervals = sorted(intervals, key=lambda x: x[0])
        merged: List[tuple[float, float]] = []

        curr_s, curr_e = sorted_intervals[0]
        for next_s, next_e in sorted_intervals[1:]:
            if next_s <= curr_e:
                # Overlapping or adjacent
                curr_e = max(curr_e, next_e)
            else:
                merged.append((curr_s, curr_e))
                curr_s, curr_e = next_s, next_e

        merged.append((curr_s, curr_e))
        return merged
