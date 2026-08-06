from dataclasses import dataclass, field
from typing import List

@dataclass
class SingleTitleSettings:
    enabled: bool = True
    text: str = ""
    align_h: str = "中央"  # 左, 中央, 右, カスタム
    align_v: str = "中央上部"  # 上/中央上部, 中央, 下/中央下部, カスタム
    x: int = 0
    y: int = 0
    font_family: str = "Hiragino Sans"
    font_path: str = ""
    font_size: int = 48
    font_color: str = "#FFFFFF"
    border_color: str = "#000000"
    border_width: int = 2
    bg_color: str = "#000000"
    bg_alpha: float = 0.0  # 0.0 ~ 1.0
    start_time: float = 0.0
    end_time: float = 15.0

@dataclass
class TitleSettingsGroup:
    title1: SingleTitleSettings = field(default_factory=lambda: SingleTitleSettings(
        enabled=True, text="講座名", align_h="中央", align_v="上", font_size=48, start_time=0.0, end_time=15.0
    ))
    title2: SingleTitleSettings = field(default_factory=lambda: SingleTitleSettings(
        enabled=True, text="コース名・回数", align_h="中央", align_v="中央", font_size=42, start_time=0.0, end_time=15.0
    ))
    title3: SingleTitleSettings = field(default_factory=lambda: SingleTitleSettings(
        enabled=True, text="日付", align_h="中央", align_v="下", font_size=32, start_time=0.0, end_time=15.0
    ))
