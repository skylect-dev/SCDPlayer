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
        ('redist/*', 'redist'),
        ('music_pack_creator/*', 'music_pack_creator'),
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
        # UI package structure
        'ui.main_window_pkg',
        'ui.main_window_pkg.startup',
        'ui.main_window_pkg.visualizer_host',
        'ui.main_window_pkg.library_controller',
        'ui.kh_rando_manager',
        'ui.conversion_manager',
        'ui.loop_editor',
        'ui.loop_editor.workers',
        'ui.loop_editor.dialogs',
        'ui.loop_editor.waveform',
        'ui.scan_overlay',
        'ui.widgets',
        'ui.styles',
        'ui.dialogs',
        'ui.help_dialog',
        'ui.volume_control',
        'ui.metadata_reader',
        'ui.musiclist_editor',
        'ui.music_pack_creator_dialog',
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
    name='SCDToolkit',
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
    name='SCDToolkit'
)
