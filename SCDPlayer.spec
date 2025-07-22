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
    ],
    hiddenimports=[],
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
        'email',
        'http',
        'urllib3',
        'xml',
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
    icon=None,  # Add icon=None or specify an .ico file path
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
