# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[
        ('vgmstream/*', 'vgmstream'),
        ('ffmpeg/*', 'ffmpeg'),
    ],
    datas=[
        ('README.md', '.'),
        ('assets/icon.svg', 'assets'),
        ('assets/icon.ico', 'assets'),
    ],
    hiddenimports=[
        # Required for auto-updater
        'email',
        'email.mime',
        'email.mime.text',
        'urllib.request',
        'urllib.parse',
        'urllib.error',
        'json',
        'tempfile',
        'shutil',
        'subprocess',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unused Python modules to reduce size
        'tkinter',
        'tkinter.*',
        'matplotlib',
        'PIL.ImageQt',
        'distutils',
        'setuptools',
        'http.server',
        'urllib3',
        'unittest',
        'pydoc',
        'doctest',
        # Exclude modules that might auto-detect FFmpeg/vgmstream DLLs
        # We'll use our manually downloaded versions instead
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
    name='SCDPlayer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',  # Use the Kingdom Hearts themed icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SCDPlayer'
)
