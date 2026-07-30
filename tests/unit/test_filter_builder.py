import pytest
from pathlib import Path
from video_silence_cutter.core.filter_builder import FilterBuilder
from video_silence_cutter.models.keep_interval import KeepInterval
from video_silence_cutter.models.title_settings import TitleSettingsGroup, SingleTitleSettings

def test_build_filter_script_with_audio_and_titles(tmp_path):
    keeps = [KeepInterval(0.0, 10.0), KeepInterval(15.0, 25.0)]
    title_grp = TitleSettingsGroup(
        title1=SingleTitleSettings(enabled=True, text="テストタイトル1"),
        title2=SingleTitleSettings(enabled=False, text=""),
        title3=SingleTitleSettings(enabled=False, text="")
    )

    script_path, v_out, a_out = FilterBuilder.build_filter_script(
        keep_intervals=keeps,
        has_audio=True,
        title_settings=title_grp,
        temp_dir=tmp_path
    )

    assert script_path.exists()
    content = script_path.read_text(encoding="utf-8")

    assert "trim=" in content
    assert "atrim=" in content
    assert "concat=n=2:v=1:a=1" in content
    assert "scale=1280:720" in content
    assert "pad=1280:720" in content
    assert "drawtext=" in content
    assert a_out == "aconcat"
    assert v_out.startswith("vtitle")

def test_build_filter_script_no_audio(tmp_path):
    keeps = [KeepInterval(0.0, 10.0)]
    script_path, v_out, a_out = FilterBuilder.build_filter_script(
        keep_intervals=keeps,
        has_audio=False,
        title_settings=None,
        temp_dir=tmp_path
    )

    content = script_path.read_text(encoding="utf-8")
    assert "concat=n=1:v=1:a=0" in content
    assert a_out == ""
