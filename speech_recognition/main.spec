# app.spec
# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],  # No need to specify here if using --add-data
    datas=[
        ('ffmpeg/bin/ffmpeg.exe', 'ffmpeg/bin'),
        ('ffmpeg/bin/ffprobe.exe', 'ffmpeg/bin'),
    ],
    hiddenimports=[
        'PyQt5',
        'torch',
        'whisper',
        'pydub',
        # Add other hidden imports if necessary
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SpeechRecognizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True for debugging
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SpeechRecognizer',
)
