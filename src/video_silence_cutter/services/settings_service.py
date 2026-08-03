import json
import shutil
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from ..utils.path_utils import get_app_support_dir

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS: Dict[str, Any] = {
    "last_open_dir": "",
    "output_dir": "",
    "silence_enabled": True,
    "silence_threshold_db": -30.0,
    "silence_min_duration": 3.0,
    "silence_padding": 0.2,
    "encoder_mode": "libx264",
    "ffmpeg_path": "",
    "ffprobe_path": "",
    "font_family": "Hiragino Sans",
    "font_path": "",
    "window_width": 1440,
    "window_height": 900,
    "window_x": -1,
    "window_y": -1,
    "splitter_sizes": [400, 1040],
    "open_finder_on_complete": True,
    "open_video_on_complete": False,
    "keep_temp_files": False,
    "title1": {
        "enabled": True,
        "text": "講座名",
        "align_h": "中央",
        "align_v": "上",
        "x": 0, "y": 0,
        "font_size": 48,
        "font_color": "#FFFFFF",
        "border_color": "#000000",
        "border_width": 2,
        "bg_color": "#000000",
        "bg_alpha": 0.0,
        "start_time": 0.0,
        "end_time": 12.0
    },
    "title2": {
        "enabled": True,
        "text": "コース名・回数",
        "align_h": "中央",
        "align_v": "中央",
        "x": 0, "y": 0,
        "font_size": 42,
        "font_color": "#FFFFFF",
        "border_color": "#000000",
        "border_width": 2,
        "bg_color": "#000000",
        "bg_alpha": 0.0,
        "start_time": 0.0,
        "end_time": 12.0
    },
    "title3": {
        "enabled": True,
        "text": "日付",
        "align_h": "中央",
        "align_v": "下",
        "x": 0, "y": 0,
        "font_size": 32,
        "font_color": "#FFFFFF",
        "border_color": "#000000",
        "border_width": 2,
        "bg_color": "#000000",
        "bg_alpha": 0.0,
        "start_time": 0.0,
        "end_time": 12.0
    }
}

class SettingsService:
    def __init__(self, custom_path: Optional[Path] = None):
        if custom_path:
            self.settings_file = custom_path
        else:
            self.settings_file = get_app_support_dir() / "settings.json"

    def load_settings(self) -> Dict[str, Any]:
        if not self.settings_file.exists():
            return self.get_defaults()

        try:
            with open(self.settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Merge with defaults to ensure missing keys are filled
            settings = self.get_defaults()
            settings.update(data)
            return settings
        except Exception as e:
            logger.error(f"Failed to load settings file (corrupted): {e}")
            self._create_backup()
            return self.get_defaults()

    def save_settings(self, settings: Dict[str, Any]) -> bool:
        try:
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            return False

    def get_defaults(self) -> Dict[str, Any]:
        return json.loads(json.dumps(DEFAULT_SETTINGS))

    def _create_backup(self) -> None:
        if self.settings_file.exists():
            backup_file = self.settings_file.with_suffix(".json.bak")
            try:
                shutil.copy(self.settings_file, backup_file)
                logger.info(f"Created backup of settings at {backup_file}")
            except Exception as e:
                logger.error(f"Failed to create settings backup: {e}")
