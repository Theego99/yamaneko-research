from setuptools import setup

APP = ['src/player.py']  # Path to your main script
DATA_FILES = ['assets/app_icon.icns']  # Include assets if necessary
OPTIONS = {
    'argv_emulation': True,
    'iconfile': 'assets/app_icon.icns',
    'packages': ['vlc'],  # Include any additional packages
    'includes': ['tkinter'],
    'plist': {
        'CFBundleName': 'DiegoMOV Player',
        'CFBundleShortVersionString': '1.1',
        'CFBundleVersion': '1.1',
        'CFBundleIdentifier': 'com.yourdomain.diegomovplayer',
        'CFBundleIconFile': 'app_icon.icns',
    },
}

setup(
    app=APP,
    name='DiegoMOV Player',
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
