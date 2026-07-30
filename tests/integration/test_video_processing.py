import os
import subprocess
import pytest
from pathlib import Path
from video_silence_cutter.core.ffmpeg_locator import FFmpegLocator
from video_silence_cutter.services.process_service import ProcessService
from video_silence_cutter.models.silence_settings import SilenceSettings
from video_silence_cutter.models.title_settings import TitleSettingsGroup, SingleTitleSettings
from video_silence_cutter.models.output_settings import OutputSettings

def create_synthetic_test_video(ffmpeg_path: Path, output_file: Path) -> bool:
    """
    Creates a 14-second synthetic MP4:
    - 0-5s: 440Hz tone (audio present)
    - 5-9s: 4s pure silence
    - 9-14s: 440Hz tone (audio present)
    """
    cmd = [
        str(ffmpeg_path),
        "-y",
        "-f", "lavfi",
        "-i", "testsrc=size=640x360:rate=30:duration=14",
        "-f", "lavfi",
        "-i", "sine=frequency=440:duration=5,aevalsrc=0:d=4,sine=frequency=440:duration=5[a]",
        "-map", "0:v",
        "-map", "[a]",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-ar", "48000",
        str(output_file)
    ]

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return res.returncode == 0 and output_file.exists()


def test_full_video_processing_integration(tmp_path):
    locator = FFmpegLocator()
    ffmpeg_path = locator.find_ffmpeg()
    ffprobe_path = locator.find_ffprobe()

    if not ffmpeg_path or not ffprobe_path:
        pytest.skip("FFmpeg/ffprobe is not installed on system. Skipping integration test.")

    test_input = tmp_path / "synthetic_14s.mp4"
    test_output = tmp_path / "synthetic_14s_cut.mp4"

    created = create_synthetic_test_video(ffmpeg_path, test_input)
    if not created:
        pytest.skip("Failed to generate synthetic test video with lavfi.")

    service = ProcessService(locator)

    silence_set = SilenceSettings(
        enabled=True,
        threshold_db=-30.0,
        min_duration=3.0,
        padding=0.2
    )

    title_set = TitleSettingsGroup(
        title1=SingleTitleSettings(enabled=True, text="結合テストタイトル", align_h="中央", align_v="上", font_size=40)
    )

    out_set = OutputSettings(
        output_dir=str(tmp_path),
        output_filename=test_output.name,
        encoder="libx264"
    )

    result = service.execute_full_pipeline(
        input_path=str(test_input),
        output_path=str(test_output),
        silence_settings=silence_set,
        title_settings=title_set,
        output_settings=out_set
    )

    assert result.success is True
    assert test_output.exists()
    assert result.silence_count >= 1
    assert result.output_duration < 14.0
    assert result.width == 1280
    assert result.height == 720
    assert result.video_codec.lower() in ["h264", "avc1"]
