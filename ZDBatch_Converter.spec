# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['PIL', 'PIL.Image', 'PIL.ImageOps', 'pillow_heif', 'pillow_avif', 'resvg_py', 'PySide6', 'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets', 'cairosvg', 'cairocffi']
hiddenimports += collect_submodules('PIL')
hiddenimports += collect_submodules('pillow_heif')
hiddenimports += collect_submodules('pillow_avif')
hiddenimports += collect_submodules('resvg_py')
try:
    hiddenimports += collect_submodules('watchdog')
except Exception:
    pass


a = Analysis(
    ['app\\main.py'],
    pathex=[],
    binaries=[('tools\\ffmpeg\\ffmpeg.exe', 'tools\\ffmpeg'), ('tools\\ffmpeg\\ffprobe.exe', 'tools\\ffmpeg')],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ZDBatch_Converter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
