# 要件定義書（REQUIREMENTS.md）

## 1. システム概要
「動画無音自動カット＆タイトル合成ツール」（VideoSilenceCutter）は、macOS上で動作するデスクトップアプリケーションです。長時間動画の無音区間を自動検出・削除し、タイトル文字（最大3段）の合成、1280×720 H.264/AAC MP4形式への統一エンコードを全自動で行います。

## 2. 機能要件

### 2.1 動画入力 & 情報取得
- 対応入力フォーマット: `.mp4`, `.mov`, `.m4v`, `.mkv`, `.avi`
- ドラッグ＆ドロップおよびファイルダイアログによる選択
- `ffprobe` を用いたメタデータ解析（解像度、fps、コーデック、ビットレート、音声ストリーム有無、再生時間等）

### 2.2 範囲指定＆無音カット
- 処理対象時間の指定（開始時刻・終了時刻、初期値は動画全体）
- FFmpeg `silencedetect` フィルターを用いた無音判定（レベル dB、最小無音秒数、前後余白秒数）
- 隣接・重複無音区間の統合、冒頭・末尾無音の適切なマージ処理
- 音声ストリームが無い動画に対するフォールバック処理

### 2.3 タイトル合成 (最大3段)
- 各段（上段・中段・下段）の個別に有効/無効化、テキスト入力
- 座標指定（数値入力および9領域プリセット指定: 中央上/中央/中央下など）
- フォント（macOS標準日本語フォント解決：ヒラギノ、Yu Gothic等）、サイズ、文字色、縁取り色・幅、背景色・透明度
- 表示開始時間・終了時間（無音カット後の出力動画タイムコード基準）
- 1280×720 基準のリアルタイムGUIプレビュー

### 2.4 映像・音声変換 & 出力
- アスペクト比維持のリサイズ (1280×720 内収め + 黒帯追加: scale + pad)
- 映像コーデック: H.264 / AVC (libx264 互換優先 / h264_videotoolbox 高速処理)
- 音声コーデック: AAC-LC (192kbps, ステレオ, 48kHz)
- CFR 29.97fps (30000/1001)、pix_fmt yuv420p、+faststart
- `filter_complex_script` を用いた長大コマンドのバッファオーバーフロー対策
- 一時ファイル拡張子（`.processing.mp4`）経由の安全書き込み

### 2.5 GUI / 非同期処理 / 進捗・ログ
- PySide6 によるモダンデスクトップUI（ダークモード/ライトモード自動対応）
- メインスレッドをブロックしない `QThread` / `QProcess` 非同期実行
- FFmpeg `-progress` 解析による進捗バー・経過時間・推定残り時間表示
- `start_new_session` によるプロセスグループ管理と、SIGTERM/SIGKILLを用いた確実なキャンセル処理
- 設定の自動保存・復元 (`~/Library/Application Support/VideoSilenceCutter/settings.json`)
- ログ保存 (`~/Library/Logs/VideoSilenceCutter/app.log`)

### 2.6 macOS アプリ化 (.app)
- PyInstaller + `build.sh` による `.app` パッケージング
- Apple Silicon (arm64) / Intel (x86_64) アーキテクチャ自動判定
- FFmpeg / ffprobe バイナリ同梱対応
- ad-hoc 署名対応

## 3. 非機能要件
- OS: macOS 13 Ventura 以降 (Apple Silicon / Intel)
- Python 3.12
- エラーハンドリング: shell=True 不使用、配列渡し、安全なパス処理
- 応答性: GUIがフリーズしない構造
