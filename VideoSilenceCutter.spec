# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path

block_cipher = None

project_dir = os.path.abspath(os.curdir)
src_dir = os.path.join(project_dir, "src")

# Data files & FFmpeg binaries bundling if present
datas = []
binaries = []

vendor_dir = os.path.join(project_dir, "vendor")
if os.path.exists(vendor_dir):
    datas.append((vendor_dir, "vendor"))

a = Analysis(
    ['app.py'],
    pathex=[project_dir, src_dir],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'video_silence_cutter',
        'video_silence_cutter.gui',
        'video_silence_cutter.core',
        'video_silence_cutter.models',
        'video_silence_cutter.services',
        'video_silence_cutter.utils',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VideoSilenceCutter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file='entitlements.plist',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VideoSilenceCutter',
)

app = BUNDLE(
    coll,
    name='VideoSilenceCutter.app',
    icon='assets/app.icns',
    bundle_identifier='jp.local.videosilencecutter',
    info_plist={
        'CFBundleName': 'VideoSilenceCutter',
        'CFBundleDisplayName': '動画無音自動カット＆タイトル合成ツール',
        'CFBundleIdentifier': 'jp.local.videosilencecutter',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'LSMinimumSystemVersion': '13.0',
        'NSHighResolutionCapable': True,
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'Video Files',
                'CFBundleTypeRole': 'Viewer',
                'LSHandlerRank': 'Alternate',
                'LSItemContentTypes': [
                    'public.mpeg-4',
                    'com.apple.quicktime-movie',
                    'public.movie',
                    'public.avi'
                ]
            }
        ]
    }
)
