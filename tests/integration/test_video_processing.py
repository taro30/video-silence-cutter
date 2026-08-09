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
        # 5〜9秒だけ振幅0（無音）になる 440Hz トーン。
        # sine を並べる書き方は FFmpeg 8 系でパースエラーになるため aevalsrc 1本で表現する。
        "-f", "lavfi",
        "-i", "aevalsrc=if(between(t\\,5\\,9)\\,0\\,0.5*sin(2*PI*440*t)):d=14:s=48000",
        "-map", "0:v",
        "-map", "1:a",
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


def test_cut_only_keeps_source_resolution_after_cancel(tmp_path):
    """
    カットのみモードは再エンコードせず元解像度のまま出力する。
    かつ、直前の処理をキャンセルした後でも実行できる（キャンセルフラグが
    残り続けて以降の実行が全て失敗する不具合の回帰テスト）。
    """
    locator = FFmpegLocator()
    ffmpeg_path = locator.find_ffmpeg()
    ffprobe_path = locator.find_ffprobe()

    if not ffmpeg_path or not ffprobe_path:
        pytest.skip("FFmpeg/ffprobe is not installed on system. Skipping integration test.")

    test_input = tmp_path / "synthetic_14s.mp4"
    test_output = tmp_path / "synthetic_14s_cutonly.mp4"

    if not create_synthetic_test_video(ffmpeg_path, test_input):
        pytest.skip("Failed to generate synthetic test video with lavfi.")

    service = ProcessService(locator)

    # 直前の実行をキャンセルした状態を再現する
    service.cancel()

    # タイトルは有効のままでも、カットのみモードでは合成・再エンコードされない
    title_set = TitleSettingsGroup(
        title1=SingleTitleSettings(enabled=True, text="無視されるタイトル", font_size=40)
    )

    result = service.execute_full_pipeline(
        input_path=str(test_input),
        output_path=str(test_output),
        silence_settings=SilenceSettings(enabled=True, threshold_db=-30.0, min_duration=3.0, padding=0.2),
        title_settings=title_set,
        output_settings=OutputSettings(
            output_dir=str(tmp_path), output_filename=test_output.name, encoder="libx264"
        ),
        cut_only=True,
    )

    assert result.success is True
    assert test_output.exists()
    # 元動画は 640x360。1280x720 へリサイズされていない = 再エンコードされていない
    assert (result.width, result.height) == (640, 360)
    assert result.output_duration < 14.0


def test_two_pass_cut_then_titles(tmp_path):
    """
    「先にトリミング＋無音カット（無再エンコード）→ 後からタイトルだけ焼き込む」
    2パス運用の検証。パス2ではカット指定がないので Stage 1 は省略され、
    入力（カット済みファイル）は壊されない。
    """
    locator = FFmpegLocator()
    ffmpeg_path = locator.find_ffmpeg()
    ffprobe_path = locator.find_ffprobe()

    if not ffmpeg_path or not ffprobe_path:
        pytest.skip("FFmpeg/ffprobe is not installed on system. Skipping integration test.")

    test_input = tmp_path / "synthetic_14s.mp4"
    if not create_synthetic_test_video(ffmpeg_path, test_input):
        pytest.skip("Failed to generate synthetic test video with lavfi.")

    service = ProcessService(locator)
    titles = TitleSettingsGroup(
        title1=SingleTitleSettings(enabled=True, text="タイトル", font_size=40)
    )

    # ── パス1: カットのみ（タイトルは有効でも合成されない） ──
    cut_file = tmp_path / "pass1_cut.mp4"
    r1 = service.execute_full_pipeline(
        input_path=str(test_input),
        output_path=str(cut_file),
        silence_settings=SilenceSettings(enabled=True, threshold_db=-30.0, min_duration=3.0, padding=0.2),
        title_settings=titles,
        output_settings=OutputSettings(
            output_dir=str(tmp_path), output_filename=cut_file.name, encoder="libx264"
        ),
        cut_only=True,
    )
    assert r1.success is True
    assert (r1.width, r1.height) == (640, 360)  # 再エンコードされていない
    assert r1.output_duration < 14.0            # 無音がカットされている

    cut_bytes_before = cut_file.read_bytes()

    # ── パス2: カット済みファイルにタイトルだけ焼き込む ──
    final_file = tmp_path / "pass2_final.mp4"
    r2 = service.execute_full_pipeline(
        input_path=str(cut_file),
        output_path=str(final_file),
        silence_settings=SilenceSettings(enabled=False),
        title_settings=titles,
        output_settings=OutputSettings(
            output_dir=str(tmp_path), output_filename=final_file.name, encoder="libx264"
        ),
        cut_only=False,
    )
    assert r2.success is True
    assert (r2.width, r2.height) == (1280, 720)  # タイトル合成のため再エンコードされる
    # パス1の尺が保たれる（二重カットされていない）
    assert abs(r2.output_duration - r1.output_duration) < 0.5
    # 入力に指定したカット済みファイルは move されず無傷で残る
    assert cut_file.read_bytes() == cut_bytes_before


def create_test_video_with_gop(ffmpeg_path: Path, output_file: Path, gop_frames: int = 60) -> bool:
    """キーフレーム間隔が既知（既定 60フレーム = 2秒）の14秒動画を作る。"""
    cmd = [
        str(ffmpeg_path), "-y",
        "-f", "lavfi", "-i", "testsrc=size=640x360:rate=30:duration=14",
        "-f", "lavfi", "-i", "aevalsrc=0.5*sin(2*PI*440*t):d=14:s=48000",
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-g", str(gop_frames), "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ar", "48000",
        str(output_file)
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return res.returncode == 0 and output_file.exists()


def test_find_next_keyframe(tmp_path):
    locator = FFmpegLocator()
    ffmpeg_path = locator.find_ffmpeg()
    if not ffmpeg_path or not locator.find_ffprobe():
        pytest.skip("FFmpeg/ffprobe is not installed on system.")

    src = tmp_path / "gop2s.mp4"
    if not create_test_video_with_gop(ffmpeg_path, src):
        pytest.skip("Failed to generate test video.")

    service = ProcessService(locator)

    # キーフレームは 0,2,4,...s にある
    assert service.ffprobe_service.find_next_keyframe(str(src), 9.0) == pytest.approx(10.0, abs=0.05)
    # ちょうどキーフレーム上ならその位置を返す
    assert service.ffprobe_service.find_next_keyframe(str(src), 8.0) == pytest.approx(8.0, abs=0.05)


def test_manual_cut_removes_whole_selected_span(tmp_path):
    """
    削除指定した範囲が「完全に」消えること。
    Stream Copy は直前のキーフレームから始まるため、対策前は削除区間の末尾
    (8.0〜9.0s) が出力に残り、尺が 11.2s ほどになっていた。
    """
    locator = FFmpegLocator()
    ffmpeg_path = locator.find_ffmpeg()
    if not ffmpeg_path or not locator.find_ffprobe():
        pytest.skip("FFmpeg/ffprobe is not installed on system.")

    src = tmp_path / "gop2s.mp4"
    if not create_test_video_with_gop(ffmpeg_path, src):
        pytest.skip("Failed to generate test video.")

    out = tmp_path / "gop2s_cut.mp4"
    service = ProcessService(locator)
    result = service.execute_full_pipeline(
        input_path=str(src),
        output_path=str(out),
        silence_settings=SilenceSettings(enabled=False, manual_cuts=[(5.0, 9.0)]),
        title_settings=TitleSettingsGroup(),
        output_settings=OutputSettings(
            output_dir=str(tmp_path), output_filename=out.name, encoder="libx264"
        ),
        cut_only=True,
    )

    assert result.success is True
    # 保持は [0,5] + [10,14] = 9.0s。削除区間の残骸(約1.2s)が混ざっていないこと
    assert result.output_duration < 9.5, "削除した区間が出力に残っています"
    assert result.output_duration > 8.5
