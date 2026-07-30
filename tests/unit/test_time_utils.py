import pytest
from video_silence_cutter.utils.time_utils import seconds_to_hms, hms_to_seconds, validate_hms

def test_seconds_to_hms_standard():
    assert seconds_to_hms(0) == "00:00:00"
    assert seconds_to_hms(3661) == "01:01:01"
    assert seconds_to_hms(86400) == "24:00:00"
    assert seconds_to_hms(100000) == "27:46:40"  # 24時間を超える動画

def test_seconds_to_hms_with_millis():
    assert seconds_to_hms(12.3456, include_millis=True) == "00:00:12.346"
    assert seconds_to_hms(0.001, include_millis=True) == "00:00:00.001"

def test_hms_to_seconds_standard():
    assert hms_to_seconds("00:00:00") == 0.0
    assert hms_to_seconds("01:01:01") == 3661.0
    assert hms_to_seconds("00:00:12.345") == pytest.approx(12.345)
    assert hms_to_seconds("27:46:40") == 100000.0

def test_hms_to_seconds_short_formats():
    assert hms_to_seconds("05:30") == 330.0
    assert hms_to_seconds("45") == 45.0

def test_invalid_formats():
    with pytest.raises(ValueError):
        seconds_to_hms(-5.0)

    with pytest.raises(ValueError):
        hms_to_seconds("-01:00:00")

    with pytest.raises(ValueError):
        hms_to_seconds("00:65:00")  # invalid minute

    with pytest.raises(ValueError):
        hms_to_seconds("invalid")

def test_validate_hms():
    assert validate_hms("01:23:45") is True
    assert validate_hms("01:23:45.678") is True
    assert validate_hms("invalid") is False
