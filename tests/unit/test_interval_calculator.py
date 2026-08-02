import pytest
from video_silence_cutter.core.interval_calculator import IntervalCalculator
from video_silence_cutter.models.silence_interval import SilenceInterval
from video_silence_cutter.models.keep_interval import KeepInterval

def test_no_silence():
    keeps = IntervalCalculator.calculate_keep_intervals(
        video_duration=20.0,
        silence_intervals=[],
        padding=0.2
    )
    assert len(keeps) == 1
    assert keeps[0] == KeepInterval(0.0, 20.0)

def test_single_silence_with_padding():
    # Silence: 10.0 ~ 15.0, Padding: 0.2 -> Cut: 10.2 ~ 14.8
    # Keep: [0.0, 10.2], [14.8, 20.0]
    silences = [SilenceInterval(10.0, 15.0)]
    keeps = IntervalCalculator.calculate_keep_intervals(
        video_duration=20.0,
        silence_intervals=silences,
        padding=0.2
    )
    assert len(keeps) == 2
    assert keeps[0] == KeepInterval(0.0, 10.2)
    assert keeps[1] == KeepInterval(14.8, 20.0)

def test_padding_cancels_short_silence():
    # Silence: 10.0 ~ 10.3, Padding: 0.2 -> cut_s=10.2, cut_e=10.1 -> cut_s >= cut_e -> No cut
    silences = [SilenceInterval(10.0, 10.3)]
    keeps = IntervalCalculator.calculate_keep_intervals(
        video_duration=20.0,
        silence_intervals=silences,
        padding=0.2
    )
    assert len(keeps) == 1
    assert keeps[0] == KeepInterval(0.0, 20.0)

def test_silence_at_start():
    # Silence: 0.0 ~ 5.0, Padding: 0.2 -> Cut: 0.2 ~ 4.8
    # Keep: [0.0, 0.2], [4.8, 20.0]
    silences = [SilenceInterval(0.0, 5.0)]
    keeps = IntervalCalculator.calculate_keep_intervals(
        video_duration=20.0,
        silence_intervals=silences,
        padding=0.2
    )
    assert len(keeps) == 2
    assert keeps[0] == KeepInterval(0.0, 0.2)
    assert keeps[1] == KeepInterval(4.8, 20.0)

def test_silence_at_end():
    # Silence: 15.0 ~ 20.0, Padding: 0.2 -> Cut: 15.2 ~ 19.8
    # Keep: [0.0, 15.2], [19.8, 20.0]
    silences = [SilenceInterval(15.0, 20.0)]
    keeps = IntervalCalculator.calculate_keep_intervals(
        video_duration=20.0,
        silence_intervals=silences,
        padding=0.2
    )
    assert len(keeps) == 2
    assert keeps[0] == KeepInterval(0.0, 15.2)
    assert keeps[1] == KeepInterval(19.8, 20.0)

def test_overlapping_and_adjacent_silences():
    # Silence 1: 5.0 ~ 10.0 (Cut: 5.2 ~ 9.8)
    # Silence 2: 9.0 ~ 14.0 (Cut: 9.2 ~ 13.8) -> Overlaps! Merged Cut: 5.2 ~ 13.8
    silences = [
        SilenceInterval(5.0, 10.0),
        SilenceInterval(9.0, 14.0)
    ]
    keeps = IntervalCalculator.calculate_keep_intervals(
        video_duration=20.0,
        silence_intervals=silences,
        padding=0.2
    )
    assert len(keeps) == 2
    assert keeps[0] == KeepInterval(0.0, 5.2)
    assert keeps[1] == KeepInterval(13.8, 20.0)

def test_custom_time_range():
    # Video: 30s. Range: 10s ~ 20s. (Cut: 0~10, 20~30)
    # Silence: 12s ~ 16s (Cut: 12.2 ~ 15.8)
    # Keeps: [10.0, 12.2], [15.8, 20.0]
    silences = [SilenceInterval(12.0, 16.0)]
    keeps = IntervalCalculator.calculate_keep_intervals(
        video_duration=30.0,
        silence_intervals=silences,
        padding=0.2,
        range_start=10.0,
        range_end=20.0
    )
    assert len(keeps) == 2
    assert keeps[0] == KeepInterval(10.0, 12.2)
    assert keeps[1] == KeepInterval(15.8, 20.0)

def test_zero_padding():
    silences = [SilenceInterval(10.0, 15.0)]
    keeps = IntervalCalculator.calculate_keep_intervals(
        video_duration=20.0,
        silence_intervals=silences,
        padding=0.0
    )
    assert len(keeps) == 2
    assert keeps[0] == KeepInterval(0.0, 10.0)
    assert keeps[1] == KeepInterval(15.0, 20.0)

def test_trimming_only_no_silence():
    # Video: 30s. Range: 5s ~ 15s. No silence.
    # Expected keep: [5.0, 15.0]
    keeps = IntervalCalculator.calculate_keep_intervals(
        video_duration=30.0,
        silence_intervals=[],
        padding=0.2,
        range_start=5.0,
        range_end=15.0
    )
    assert len(keeps) == 1
    assert keeps[0] == KeepInterval(5.0, 15.0)
