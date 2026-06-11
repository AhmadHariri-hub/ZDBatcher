# ZDBatcher

A Windows desktop batch media automation tool built to process repetitive file and media workflows quickly, including conversion, resizing, renaming, sorting, batch folder creation, and watch-folder automation.

## Status

Working prototype / active development.

## Current Features

- Image conversion (JPG, PNG, WebP, AVIF, SVG, HEIC, BMP, TIFF, etc.)
- Image resizing and compression
- Video conversion (via FFmpeg)
- Video resizing and compression
- Audio conversion and extraction from video
- Mixed media conversion and resizing
- File sorting into organized folder structures
- Batch folder creation by file count or folder size
- File renaming with numbering, prefixes, and sorting
- Watch folder automation (auto-processes new files)

### Performance Note

Converted a 6 GB video to MP3 in around 20 seconds with clean output.

## Requirements

- Windows
- Python 3.14+
- PySide6
- FFmpeg / FFprobe (required for audio and video tools)

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.main
```

## Install FFmpeg

FFmpeg is required for media conversion (audio and video tools). The public repository does not bundle FFmpeg binaries.

To install FFmpeg locally for this project, either click **Install FFmpeg** in the app sidebar when FFmpeg is missing, or run:

```powershell
.\scripts\install_ffmpeg.ps1
```

Both options download a Windows FFmpeg release archive and extract only `ffmpeg.exe` and `ffprobe.exe` into the ignored local folder `tools\ffmpeg\`.

You can also install FFmpeg globally and make it available through your system `PATH` if you prefer. ZDBatcher checks local `tools\ffmpeg\` first, then falls back to `PATH`.

If FFmpeg is missing, the app will show a clear error message for tools that require it, while image-only tools will continue to work.

## How to Use

1. Launch the app with `python -m app.main`
2. Select a tool from the sidebar navigation
3. Choose input files or folders
4. Configure output settings for your task
5. Click the action button to start processing
6. Monitor progress and log output in the bottom panel

**Watch Folder mode** monitors a directory and automatically processes new files based on your configured rules. Use carefully - it processes files automatically.

## Known Limitations

- Active development / working prototype
- Some advanced workflows may still need stabilization
- Watch folder automation should be used carefully because it processes files automatically
- Packaging/build setup is still evolving (two spec files exist for alternate PyInstaller configurations)

## Planned Improvements

- Better error handling and edge-case coverage
- More stable watch-folder behavior
- Cleaner packaging and installer
- More conversion presets and quality controls
- Better progress and log reporting
