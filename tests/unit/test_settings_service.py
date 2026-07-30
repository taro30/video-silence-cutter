import pytest
import json
from video_silence_cutter.services.settings_service import SettingsService

def test_load_non_existent_file(tmp_path):
    settings_file = tmp_path / "settings.json"
    service = SettingsService(custom_path=settings_file)
    data = service.load_settings()

    assert data["silence_threshold_db"] == -30.0
    assert data["silence_padding"] == 0.2
    assert data["title1"]["text"] == "講座名"

def test_save_and_load(tmp_path):
    settings_file = tmp_path / "settings.json"
    service = SettingsService(custom_path=settings_file)

    data = service.get_defaults()
    data["silence_threshold_db"] = -25.0
    data["last_open_dir"] = "/Users/test/Movies"

    assert service.save_settings(data) is True

    loaded = service.load_settings()
    assert loaded["silence_threshold_db"] == -25.0
    assert loaded["last_open_dir"] == "/Users/test/Movies"

def test_corrupted_json_backup(tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text("{ corrupted json ...", encoding="utf-8")

    service = SettingsService(custom_path=settings_file)
    data = service.load_settings()

    # Defaults restored
    assert data["silence_threshold_db"] == -30.0
    # Backup created
    backup_file = tmp_path / "settings.json.bak"
    assert backup_file.exists()
    assert backup_file.read_text(encoding="utf-8") == "{ corrupted json ..."
