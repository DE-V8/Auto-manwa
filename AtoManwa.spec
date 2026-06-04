# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Ato Manwa - Hindi Video Generator
Build command: pyinstaller AtoManwa.spec --clean
"""

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all data files needed by libraries
datas = []

# customtkinter needs its theme/asset files
datas += collect_data_files('customtkinter')

# moviepy needs its config/preset files
datas += collect_data_files('moviepy')

# edge_tts needs its voice data
datas += collect_data_files('edge_tts')

# google-genai SDK assets
datas += collect_data_files('google.genai', includes=['**/*.json'])

# Include the app's own bundled data folders
datas += [
    ('data',     'data'),      # music folder, sample_chapter, etc.
    ('tools',    'tools'),     # comics-downloader.exe
]

if os.path.exists('config.json'):
    datas += [('config.json', '.')]


# Hidden imports that PyInstaller misses via static analysis
hiddenimports = [
    # scripts package
    'scripts',
    'scripts.gemini_helper',
    'scripts.tts_helper',
    'scripts.video_helper',
    # moviepy internals
    'moviepy',
    'moviepy.audio.fx',
    'moviepy.audio.fx.AudioLoop',
    'moviepy.audio.fx.MultiplyVolume',
    'moviepy.video.fx',
    # PIL / Pillow
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'PIL.ImageFilter',
    # async / tts
    'asyncio',
    'edge_tts',
    # google AI
    'google.genai',
    'google.genai.types',
    'pydantic',
    # PDF support
    'fitz',        # PyMuPDF
    # misc
    'numpy',
    'dotenv',
    'python_dotenv',
    'tkinter',
    'tkinter.filedialog',
    'tkinter.messagebox',
]

a = Analysis(
    ['gui.py'],
    pathex=['.', 'scripts'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'scipy', 'pandas', 'jupyter',
        'IPython', 'notebook', 'sphinx',
    ],
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
    name='AtoManwa',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # No console window (GUI app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # Set to 'icon.ico' if you have one
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AtoManwa',
)
