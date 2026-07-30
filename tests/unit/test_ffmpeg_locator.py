import pytest
from pathlib import Path
from video_silence_cutter.core.ffmpeg_locator import FFmpegLocator

def test_find_ffmpeg_and_ffprobe_system():
    locator = FFmpegLocator()
    ffmpeg_path = locator.find_ffmpeg()
    ffprobe_path = locator.find_ffprobe()

    if ffmpeg_path is None or ffprobe_path is None:
        pytest.skip("FFmpeg / ffprobe is not installed on this system. Skipping system binary test.")

    assert ffmpeg_path.exists()
    assert ffprobe_path.exists()

def test_validate_ffmpeg():
    locator = FFmpegLocator()
    ffmpeg_path = locator.find_ffmpeg()
    if ffmpeg_path is None:
        pytest.skip("FFmpeg is not installed on this system.")

    valid, msg = locator.validate_ffmpeg(ffmpeg_path)
    assert valid is True
    assert "ffmpeg version" in msg.lower() or "version" in msg.lower()


def test_custom_ffmpeg_path(tmp_path):
    fake_ffmpeg = tmp_path / "ffmpeg"
    fake_ffmpeg.write_text("#!/bin/sh\necho ffmpeg version 6.0")
    fake_ffmpeg.chmod(0o755)

    locator = FFmpegLocator(custom_ffmpeg=str(fake_ffmpeg))
    found = locator.find_ffmpeg()
    assert found == fake_ffmpeg
