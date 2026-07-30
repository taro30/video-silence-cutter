# 設計書（DESIGN.md）

## 1. 全体アーキテクチャ
本アプリケーションは PySide6 による GUI 層、ビジネスロジックを管理する Service 層、純粋なドメイン計算および FFmpeg 連携を担う Core 層、データモデル層に分離されています。

```
+-------------------------------------------------------+
|                    PySide6 GUI                        |
| (MainWindow, PreviewWidget, IntervalTable, Settings)  |
+---------------------------+---------------------------+
                            |
+---------------------------v---------------------------+
|                   Services Layer                      |
| (ProcessService, FontService, SettingsService, etc.)   |
+---------------------------+---------------------------+
                            |
+---------------------------v---------------------------+
|                     Core Layer                        |
|  - FFmpegLocator      - SilenceDetector / Parser      |
|  - FFprobeService     - IntervalCalculator (Pure)     |
|  - FilterBuilder      - VideoProcessor (Runner)       |
|  - TitleRenderer      - OutputValidator               |
+---------------------------+---------------------------+
                            |
+---------------------------v---------------------------+
|               Data Models & Utilities                 |
| (VideoInfo, SilenceSettings, SilenceInterval, etc.)   |
+-------------------------------------------------------+
```

## 2. モジュール設計と責務

### 2.1 `models/`
- `video_info.py`: 動画・音声メタデータ（解像度、fps、duration、codecs、channels等）
- `silence_interval.py`: 検出された無音区間データモデル `SilenceInterval(start, end)`
- `keep_interval.py`: 残す動画区間データモデル `KeepInterval(start, end)`
- `silence_settings.py`: 無音判定用パラメーター（enabled, threshold_db, min_duration, padding）
- `title_settings.py`: タイトル設定モデル（text, font, size, colors, position, time_range）
- `output_settings.py`: 出力パラメーター（encoder, bitrate, preset, paths）
- `process_result.py`: 処理結果統計情報

### 2.2 `core/`
- `ffmpeg_locator.py`: .app内、vendor/、Homebrew(/opt/homebrew, /usr/local)、PATHからFFmpeg/ffprobeを探索
- `ffprobe_service.py`: 動画ファイルのJSONメタデータ解析
- `silence_parser.py`: silencedetect ログ（silence_start, silence_end）のパース処理
- `interval_calculator.py`: 【純粋関数】無音区間＋指定時間範囲＋余白から「残す区間 (KeepInterval)」を正確に算出するコアロジック
- `filter_builder.py`: trim/atrim/concat/scale/pad/drawtext などの FFmpeg `filter_complex` スクリプト生成
- `video_processor.py`: `subprocess.Popen` (start_new_session=True) を利用したFFmpeg実行制御と進捗追跡
- `output_validator.py`: 出力完了後の動画メタデータ・整合性検証

### 2.3 `services/`
- `settings_service.py`: `settings.json` の読込・保存・バックアップ処理
- `font_service.py`: macOS上の日本語フォント (.ttf/.otf/.ttc) ファイルパス解決
- `preview_service.py`: 1280×720 プレビュー用タイトルのレンダリングオーバーレイ
- `process_service.py`: 全処理（ffprobe -> detect -> keep calculation -> filter build -> encode -> validate）のオーケストレーション

### 2.4 `gui/`
- `main_window.py`: メインウィンドウ、レイアウト配置、イベントバインド
- `preview_widget.py`: 動画静止画＋タイトル表示のプレビュー描画（ドラッグ操作対応）
- `worker.py`: QThread を用いた バックグラウンドタスクワーカー

## 3. 無音カット区間計算アルゴリズム（純粋関数）
入力:
- 動画総時間 $T_{total}$
- 処理対象区間 $[T_{start}, T_{end}]$
- 無音区間リスト $[ (s_1, e_1), (s_2, e_2), \dots ]$
- 余白 $P$

手順:
1. 対象外区間（0 ~ $T_{start}$、および $T_{end}$ ~ $T_{total}$）を削除対象区間として扱うかフィルター
2. 各無音区間 $(s_i, e_i)$ に対し、余白を適用した実削除区間 $(s_i + P, e_i - P)$ を計算。ただし $s_i + P \ge e_i - P$ の場合は削除なし
3. 隣接・重なり合う削除区間をマージ
4. 残存する非削除区間 $[k_{start}, k_{end}]$ を順次抽出して `KeepInterval` リストを出力

## 4. FFmpeg フィルター構築設計
`filter_complex_script` ファイルを使用：
- 各 `KeepInterval` に対し `[0:v]trim=start=...:end=...,setpts=PTS-STARTPTS[v0];` および `[0:a]atrim=start=...:end=...,asetpts=PTS-STARTPTS[a0];`
- 映像・音声を `concat=n=N:v=1:a=1` で結合
- 1280×720 スケーリング＆黒帯追加: `scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps=30000/1001,format=yuv420p`
- タイトルテキスト（最大3段）を `drawtext=textfile=...` で合成
