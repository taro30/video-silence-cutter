# 動画無音自動カット＆タイトル合成ツール (VideoSilenceCutter)

長時間動画（講座動画、オンライン会議、画面収録、解説動画など）の無音部分を自動で検出し、指定した余白を残してカットするとともに、冒頭に最大3段のタイトル文字を合成し、高音質・高品質な1280×720 MP4動画として一元出力するmacOS用デスクトップアプリケーションです。

---

## 🌟 主な機能

1. **自動無音検出 & 余白カット**
   - FFmpeg `silencedetect` を用いた高精度な無音解析
   - 無音区間の前後に指定した余白（初期値: 0.2秒）を残す自然なカット
   - 冒頭・末尾の無音や隣接・重なり合う無音の自動統合マージ処理

2. **最大3段の日本語タイトル合成**
   - 上段（講座名）、中段（コース名・回数）、下段（日付）などのタイトル設定
   - フォントサイズ、文字色、縁取り（色・幅）、背景ボックス（透明度）の自由設定
   - 画面中央上部、中央、中央下部などのプリセットおよびカスタム座標指定

3. **リアルタイム1280×720プレビュー**
   - 動画の代表フレーム上にタイトル配置をリアルタイムプレビュー
   - 16:9 以外の動画アスペクト比を維持し、黒帯を自動補填

4. **1280×720 H.264 / AAC MP4 高速出力**
   - Apple Silicon ハードウェアエンコード（`h264_videotoolbox`）および互換性優先モード（`libx264`）対応
   - 1500kbps 29.97fps CFR 映像 + 192kbps 48kHz AAC 音声

5. **安全・フリーズしないGUI**
   - PySide6 による非同期処理（QThread）で長時間エンコード中も画面がフリーズしない
   - プロセスグループ切断による完全な処理キャンセル機能
   - 設定の自動保存・復元およびローテーションログ記録

---

## 💻 対応環境

- **対応OS:** macOS 13.0 Ventura 以降 (推奨: macOS 14 Sonoma 以降)
- **CPU:** Apple Silicon (M1/M2/M3/M4) 優先 / Intel Mac 対応
- **Python:** 3.12 以降
- **外部依存:** FFmpeg, ffprobe

---

## 🚀 セットアップと起動手順

### 1. Homebrew および FFmpeg / Python のインストール

Mac のターミナルを開き、以下のコマンドで Homebrew、Python 3.12、および FFmpeg をインストールします。

```bash
# 1. Homebrewのインストール (未インストールの場合は公式サイトの手順に従ってください)
# https://brew.sh/

# 2. FFmpeg のインストール
brew install ffmpeg

# 3. Python 3.12 のインストール
brew install python@3.12
```

### 2. プロジェクトの取得と仮想環境の構築

```bash
# プロジェクトフォルダへ移動
cd video-silence-cutter

# Python 3.12 仮想環境の作成
python3.12 -m venv .venv

# 仮想環境の有効化
source .venv/bin/activate

# 依存ライブラリのインストール
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 3. アプリケーションの起動

```bash
python app.py
```

---

## 🧪 テストの実行方法

本プロジェクトはテスト駆動開発（TDD）に基づき構築されています。

```bash
# 単体テストおよび結合テストの実行
pytest
```

---

## 📦 macOS 用 .app (VideoSilenceCutter.app) の作成方法

PyInstaller と `build.sh` を使用して、macOS 用のスタンドアロン `.app` アプリを作成できます。

```bash
# ビルドスクリプトの実行
chmod +x build.sh
./build.sh
```

成果物は `dist/VideoSilenceCutter.app` に生成されます。

### 未署名 .app の起動方法 (macOS セキュリティ対応)
作成した `.app` を初めて開く際は、以下の手順で起動してください：

1. Finder で `dist/VideoSilenceCutter.app` を選択し、**右クリック（または Control + クリック）** します。
2. メニューから **「開く」** を選択します。
3. 警告ダイアログが表示されたら **「開く」** をクリックします。

---

## 📂 設定ファイルとログの保存場所

- **設定ファイル:** `~/Library/Application Support/VideoSilenceCutter/settings.json`
- **ログファイル:** `~/Library/Logs/VideoSilenceCutter/app.log`

---

## 📁 プロジェクト構成

```
video-silence-cutter/
├── app.py                      # メインエントリーポイント
├── pyproject.toml              # プロジェクト設定
├── requirements.txt            # 本番用依存関係
├── requirements-dev.txt        # 開発用依存関係
├── pytest.ini                  # Pytest 設定
├── build.sh                    # .app ビルド・テスト自動化スクリプト
├── VideoSilenceCutter.spec     # PyInstaller スペックファイル
├── entitlements.plist          # macOS コード署名設定
├── REQUIREMENTS.md             # 要件定義書
├── DESIGN.md                   # 設計書
├── IMPLEMENTATION_PLAN.md      # 実装計画書
├── README.md                   # 本ドキュメント
├── src/
│   └── video_silence_cutter/
│       ├── application.py      # GUI アプリケーション初期化
│       ├── gui/                # PySide6 GUI コンポーネント群
│       ├── core/               # FFmpeg, 解析, 計算コアロジック
│       ├── models/             # データクラスモデル群
│       ├── services/           # 設定, フォント, プレビュー等サービス群
│       └── utils/              # 時間変換, パス操作, ログ等のユーティリティ
└── tests/
    ├── unit/                   # 単体テスト群
    └── integration/            # FFmpeg lavfi を使用した結合テスト
```
