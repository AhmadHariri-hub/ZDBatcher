@echo off
setlocal

set "FFMPEG_TARGET=tools\ffmpeg\ffmpeg.exe"
set "FFPROBE_TARGET=tools\ffmpeg\ffprobe.exe"
set "PYINSTALLER=py -m PyInstaller"

if exist ".venv\Scripts\pyinstaller.exe" (
    set "PYINSTALLER=.venv\Scripts\pyinstaller.exe"
)

set "BUNDLE_FFMPEG=0"
if exist "%FFMPEG_TARGET%" if exist "%FFPROBE_TARGET%" (
    set "BUNDLE_FFMPEG=1"
)

if "%BUNDLE_FFMPEG%"=="0" (
    echo ------------------------------------------------------------
    echo FFmpeg binaries not found in tools\ffmpeg\
    echo The app will use system PATH to find ffmpeg and ffprobe.
    echo To bundle FFmpeg, copy ffmpeg.exe and ffprobe.exe into
    echo tools\ffmpeg\ before building.
    echo ------------------------------------------------------------
    echo.
)

%PYINSTALLER% ^
    --noconfirm ^
    --clean ^
    --windowed ^
    --onefile ^
    --name ZDBatch_Converter ^
    --collect-submodules PIL ^
    --collect-submodules pillow_heif ^
    --collect-submodules pillow_avif ^
    --collect-submodules resvg_py ^
    --hidden-import PIL ^
    --hidden-import PIL.Image ^
    --hidden-import PIL.ImageOps ^
    --hidden-import pillow_heif ^
    --hidden-import pillow_avif ^
    --hidden-import resvg_py ^
    --hidden-import PySide6 ^
    --hidden-import PySide6.QtCore ^
    --hidden-import PySide6.QtGui ^
    --hidden-import PySide6.QtWidgets ^
    --hidden-import cairosvg ^
    --hidden-import cairocffi ^
    app\main.py
