# your_script.spec
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

import os

# Define the VLC directory path
base_path = os.path.abspath(os.path.dirname(__name__))
vlc_path = os.path.join(base_path, 'vlc')

# Add VLC binaries and plugins
binaries = [
    (os.path.join(vlc_path, 'libvlc.dll'), 'vlc'),
    (os.path.join(vlc_path, 'libvlccore.dll'), 'vlc'),
]

datas = [
    (os.path.join(vlc_path, 'plugins'), os.path.join('vlc', 'plugins')),
]

a = Analysis(
    ['DiegoMOV_Player.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DiegoMOV_Player',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='assets/app_icon.ico',
)
