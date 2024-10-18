from setuptools import setup

APP = ['your_script.py']
import glob

plugins = glob.glob('vlc/plugins/**/*', recursive=True)

DATA_FILES = [
    ('assets', ['assets/app_icon.icns']),
    ('vlc', ['vlc/libvlc.dylib', 'vlc/libvlccore.dylib']),
    ('vlc/plugins', plugins),
]

OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'assets/app_icon.icns',
    'includes': ['sip', 'PyQt5', 'vlc'],
    'packages': ['vlc'],
    'plist': {
        'CFBundleIdentifier': 'com.yourcompany.yourapp',
        'NSHighResolutionCapable': True,
    },
}

setup(
    app=APP,
    name='DiegoMOV Player',
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
