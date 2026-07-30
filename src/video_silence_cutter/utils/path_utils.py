import os
from pathlib import Path
import tempfile
import sys

APP_NAME = "VideoSilenceCutter"

def get_app_support_dir() -> Path:
    base = Path.home() / "Library" / "Application Support" / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base

def get_app_logs_dir() -> Path:
    base = Path.home() / "Library" / "Logs" / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base

def get_bundle_resource_dir() -> Path:
    if getattr(sys, 'frozen', False):
        # PyInstaller bundled .app
        return Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent))
    return Path(__file__).resolve().parents[3]

def create_temp_dir() -> tempfile.TemporaryDirectory:
    return tempfile.TemporaryDirectory(prefix="vsc_")
