#!/bin/bash
set -e

echo "=== 🚀 VideoSilenceCutter macOS .app ビルド開始 ==="

# 1. Check Virtual Environment
if [ -d ".venv" ]; then
    echo "• 仮想環境 .venv を有効化します..."
    source .venv/bin/activate
fi

# 2. Run pytest
echo "• pytest テストを実行します..."
python -m pytest

# 3. Clean previous build artifacts
echo "• 既存の build/ および dist/ フォルダをクリアします..."
rm -rf build dist

# 4. Check CPU Architecture
ARCH=$(uname -m)
echo "• システムアーキテクチャ: ${ARCH}"

# 5. Run PyInstaller
echo "• PyInstaller で .app パッケージを作成中..."
pyinstaller --clean VideoSilenceCutter.spec

APP_PATH="dist/VideoSilenceCutter.app"

if [ -d "${APP_PATH}" ]; then
    echo "• .app の作成に成功しました: ${APP_PATH}"
    
    # 6. Ad-hoc Signing
    echo "• ad-hoc コード署名を実行します..."
    codesign --force --deep --sign - "${APP_PATH}" || echo "⚠️ ad-hoc 署名警告 (無視して継続します)"

    echo ""
    echo "=================================================="
    echo "🎉 ビルドが正常に完了しました！"
    echo "成果物: ${APP_PATH}"
    echo ""
    echo "【未署名/ローカル.appの起動方法】"
    echo "1. Finderで ${APP_PATH} を右クリック（Control+クリック）"
    echo "2. 「開く」を選択し、ダイアログで「開く」をクリックしてください。"
    echo "=================================================="
else
    echo "❌ ビルドに失敗しました。.app が生成されていません。"
    exit 1
fi
