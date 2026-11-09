# -*- mode: python ; coding: utf-8 -*-
import sys
import os

block_cipher = None

# ── Datas collection ────────────────────────────────────────────────────────
# NOTE: config.json (contains user API keys) must NEVER be bundled.
datas = [
    ('components', 'components'),
    ('widgets', 'widgets'),
    ('dialogs', 'dialogs'),
]

# ── Hidden imports collection ───────────────────────────────────────────────
hiddenimports = [
    # Application modules
    'components.transcription_worker',
    'components.updater',
    'widgets.speaker_manager',
    'dialogs.speaker_dialog',
    'dialogs.update_dialog',

    # Cloud & Network
    'assemblyai',
    'httpx',
    'httpcore',
    'requests',
    'urllib3',
    'dotenv',
]

# Deduplicate
hiddenimports = sorted(list(set(hiddenimports)))

# ── Analysis ────────────────────────────────────────────────────────────────
a = Analysis(
    ['main_gui.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'IPython', 'jupyter', 
        'torch', 'torchaudio', 'torchvision', 'whisperx', 
        'pyannote', 'ctranslate2', 'transformers', 
        'tokenizers', 'faster_whisper', 'lightning', 
        'pytorch_lightning', 'huggingface_hub', 'numpy', 'pandas', 'scipy', 'sklearn'
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
    name='CoelhoTranscriber',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # Windowed GUI application
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='components/icons/icon.ico' if os.path.exists('components/icons/icon.ico') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='CoelhoTranscriber',
)
