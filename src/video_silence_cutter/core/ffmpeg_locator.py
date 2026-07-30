import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple
from ..utils.path_utils import get_bundle_resource_dir

class FFmpegLocator:
    def __init__(self, custom_ffmpeg: Optional[str] = None, custom_ffprobe: Optional[str] = None):
        self.custom_ffmpeg = custom_ffmpeg
        self.custom_ffprobe = custom_ffprobe

    def find_ffmpeg(self) -> Optional[Path]:
        if self.custom_ffmpeg and Path(self.custom_ffmpeg).is_file():
            if os.access(self.custom_ffmpeg, os.X_OK):
                return Path(self.custom_ffmpeg)

        bundle_dir = get_bundle_resource_dir()
        candidates = [
            bundle_dir / "Contents" / "Resources" / "bin" / "ffmpeg",
            bundle_dir / "vendor" / "macos" / "arm64" / "ffmpeg",
            bundle_dir / "vendor" / "macos" / "x86_64" / "ffmpeg",
            bundle_dir / "vendor" / "ffmpeg",
            Path(sys.executable).parent / "ffmpeg",
            Path("/opt/homebrew/bin/ffmpeg"),
            Path("/usr/local/bin/ffmpeg"),
        ]

        for cand in candidates:
            if cand.is_file() and os.access(cand, os.X_OK):
                return cand

        which_path = shutil.which("ffmpeg")
        if which_path:
            return Path(which_path)

        return None

    def find_ffprobe(self) -> Optional[Path]:
        if self.custom_ffprobe and Path(self.custom_ffprobe).is_file():
            if os.access(self.custom_ffprobe, os.X_OK):
                return Path(self.custom_ffprobe)

        bundle_dir = get_bundle_resource_dir()
        candidates = [
            bundle_dir / "Contents" / "Resources" / "bin" / "ffprobe",
            bundle_dir / "vendor" / "macos" / "arm64" / "ffprobe",
            bundle_dir / "vendor" / "macos" / "x86_64" / "ffprobe",
            bundle_dir / "vendor" / "ffprobe",
            Path(sys.executable).parent / "ffprobe",
            Path("/opt/homebrew/bin/ffprobe"),
            Path("/usr/local/bin/ffprobe"),
        ]

        for cand in candidates:
            if cand.is_file() and os.access(cand, os.X_OK):
                return cand

        which_path = shutil.which("ffprobe")
        if which_path:
            return Path(which_path)

        return None

    def validate_ffmpeg(self, ffmpeg_path: Path) -> Tuple[bool, str]:
        if not ffmpeg_path or not ffmpeg_path.exists():
            return False, "FFmpegバイナリが存在しません。"

        try:
            res = subprocess.run(
                [str(ffmpeg_path), "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            if res.returncode != 0:
                return False, f"FFmpegの実行に失敗しました (exit code: {res.returncode})"

            output = res.stdout + res.stderr
            return True, output.splitlines()[0] if output else "FFmpeg version OK"
        except Exception as e:
            return False, f"FFmpeg実行時例外: {str(e)}"
