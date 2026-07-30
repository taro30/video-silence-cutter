# 実装計画書 (IMPLEMENTATION_PLAN.md)

## 1. 概要
「動画無音自動カット＆タイトル合成ツール」（VideoSilenceCutter）のTDD（テスト駆動開発）に基づく段階的実装計画です。

## 2. 段階的実装ステップ

### 第1段階: プロジェクト初期化 & コアロジック & TDD
1. プロジェクト構造・仮想環境設定 (`pyproject.toml`, `requirements.txt`, `pytest.ini`)
2. `utils` 実装 (時間変換, パス操作, ログ設定) & 単体テスト (`test_time_utils.py`)
3. `models` データクラス定義 (`VideoInfo`, `SilenceInterval`, `KeepInterval`, `SilenceSettings`, `TitleSettings`, `OutputSettings`)
4. `core/ffmpeg_locator.py` & 単体テスト (`test_ffmpeg_locator.py`)
5. `core/silence_parser.py` & 単体テスト (`test_silence_parser.py`)
6. `core/interval_calculator.py` 【核心の純粋関数】 & 単体テスト (`test_interval_calculator.py`)
7. `services/settings_service.py` & 単体テスト (`test_settings_service.py`)

### 第2段階: FFmpeg 連携 & 結合テスト
1. `core/ffprobe_service.py` 実装 & テスト
2. `core/filter_builder.py` (trim/atrim/concat/scale/pad/drawtext) & 単体テスト (`test_filter_builder.py`)
3. `core/video_processor.py` (subprocess/進捗追跡/SIGKILLプロセスグループ切断)
4. `core/output_validator.py` 実装
5. FFmpeg / lavfi を使ったダミー動画生成による結合テスト (`test_video_processing.py`)

### 第3段階: タイトル合成 & フォント探索 & プレビュー
1. `services/font_service.py` (macOS ヒラギノ/Yu Gothic 等のフォント解決)
2. `core/title_renderer.py` (drawtextテキストファイル出力とエスケープ)
3. `services/preview_service.py` (代表フレーム抽出しタイトル合成プレビュー生成)

### 第4段階: PySide6 GUI 実装
1. `gui/main_window.py` Layout (動画選択, 設定パネル, プレビュー, プログレスバー, ログ)
2. `gui/preview_widget.py` (ドラッグ＆ドロップ対応タイトルプレビュー)
3. `gui/interval_table.py` (解析結果テーブル)
4. `gui/settings_dialog.py` & `completion_dialog.py`
5. `gui/worker.py` (QThread非同期処理 & 進捗通知 & キャンセルハンドリング)
6. macOS メニューバー & ショートカット実装

### 第5段階: macOS .app アプリ化 & ドキュメント & 最終検証
1. `VideoSilenceCutter.spec`, `entitlements.plist`, `build.sh` 作成
2. PyInstaller による macOS .app ビルド & ad-hoc 署名
3. 初心者向け README.md 作成
4. 全ユニットテスト・結合テスト実行及び .app の動作検証

## 3. 検証計画

### 3.1 自動テスト (pytest)
- `pytest tests/unit` で単体テスト実行
- `pytest tests/integration` で FFmpeg lavfi 生成動画を用いた結合テスト実行

### 3.2 手動/動作検証
- ダミー動画またはテスト用MP4のドラッグ＆ドロップ動作
- 無音カット解析 & テーブル表示
- タイトルテキスト表示位置・装飾のプレビュー確認
- エンコード完了後の MP4 メタデータ検証 (1280x720, H.264, AAC, 29.97fps)
- `.app` 起動確認
