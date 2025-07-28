# -*- mode: python ; coding: utf-8 -*-

# Note: Block cipher encryption was removed in PyInstaller v6.0+
# We'll use other antivirus evasion techniques: UPX disabled, version info, proper exclusions
block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[
        ('vgmstream/*', 'vgmstream'),
        ('ffmpeg/*', 'ffmpeg'),
        ('khpc_tools/*', 'khpc_tools'),
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
        # Audio processing dependencies
        'numpy',
        'soundfile',
        'mutagen',
        # PyQt5 related
        'PyQt5.QtCore',
        'PyQt5.QtWidgets',
        'PyQt5.QtGui',
        'PyQt5.QtMultimedia',
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
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SCDPlayer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,  # Disable strip to avoid Windows tool warnings
    upx=False,  # Disable UPX compression as it can trigger detection
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',  # Use the Kingdom Hearts themed icon
    version='version_info.py',  # Add version info to make it look more legitimate
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,  # Disable strip to avoid Windows tool warnings
    upx=False,  # Disable UPX for all files
    upx_exclude=[],
    name='SCDPlayer'
)
