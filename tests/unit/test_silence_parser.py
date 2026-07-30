import pytest
from video_silence_cutter.core.silence_parser import SilenceParser
from video_silence_cutter.models.silence_interval import SilenceInterval

def test_parse_empty_log():
    intervals = SilenceParser.parse_log("")
    assert intervals == []

def test_parse_no_silence():
    log = """
    frame= 100 fps=30 q=28.0 size=    1024kB time=00:00:03.33 bitrate=2516.5kbits/s speed= 3.3x
    """
    assert SilenceParser.parse_log(log) == []

def test_parse_single_interval():
    log = """
    [silencedetect @ 0x7f8844504100] silence_start: 10.5
    [silencedetect @ 0x7f8844504100] silence_end: 15.2 | silence_duration: 4.7
    """
    intervals = SilenceParser.parse_log(log)
    assert len(intervals) == 1
    assert intervals[0] == SilenceInterval(start=10.5, end=15.2)

def test_parse_multiple_intervals():
    log = """
    [silencedetect @ 0x1] silence_start: 0.0
    [silencedetect @ 0x1] silence_end: 3.5 | silence_duration: 3.5
    some other ffmpeg log output...
    [silencedetect @ 0x1] silence_start: 12.25
    [silencedetect @ 0x1] silence_end: 18.75 | silence_duration: 6.5
    """
    intervals = SilenceParser.parse_log(log)
    assert len(intervals) == 2
    assert intervals[0] == SilenceInterval(start=0.0, end=3.5)
    assert intervals[1] == SilenceInterval(start=12.25, end=18.75)

def test_parse_unclosed_silence_with_duration():
    log = """
    [silencedetect @ 0x1] silence_start: 50.0
    """
    intervals = SilenceParser.parse_log(log, total_duration=60.0)
    assert len(intervals) == 1
    assert intervals[0] == SilenceInterval(start=50.0, end=60.0)

def test_parse_garbage_lines():
    log = """
    random noise line 123
    silence_start: invalid
    silence_start: 5.0
    silence_end: 10.0
    """
    intervals = SilenceParser.parse_log(log)
    assert len(intervals) == 1
    assert intervals[0] == SilenceInterval(start=5.0, end=10.0)
