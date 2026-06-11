import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable


FFMPEG_ARCHIVE_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
DOWNLOAD_TIMEOUT_SECONDS = 30
DOWNLOAD_CHUNK_SIZE = 1024 * 256


class FfmpegInstallError(RuntimeError):
    pass


ProgressCallback = Callable[[str], None]


def install_ffmpeg(progress: ProgressCallback | None = None) -> tuple[Path, Path]:
    target_dir = _target_dir()
    ffmpeg_path = target_dir / "ffmpeg.exe"
    ffprobe_path = target_dir / "ffprobe.exe"

    if ffmpeg_path.is_file() and ffprobe_path.is_file():
        _emit(progress, "FFmpeg is already installed locally.")
        return ffmpeg_path, ffprobe_path

    temp_dir = Path(tempfile.mkdtemp(prefix="zdbatcher-ffmpeg-"))
    archive_path = temp_dir / "ffmpeg-release-essentials.zip"
    partial_path = archive_path.with_suffix(".zip.download")

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        _download_archive(partial_path, archive_path, progress)
        _extract_tools(archive_path, temp_dir, ffmpeg_path, ffprobe_path, progress)

        if not ffmpeg_path.is_file():
            raise FfmpegInstallError("ffmpeg.exe was not installed.")

        if not ffprobe_path.is_file():
            raise FfmpegInstallError("ffprobe.exe was not installed.")

        _emit(progress, "FFmpeg installed successfully.")
        return ffmpeg_path, ffprobe_path
    except FfmpegInstallError:
        raise
    except urllib.error.URLError as exc:
        raise FfmpegInstallError("Could not download FFmpeg. Check your internet connection and try again.") from exc
    except TimeoutError as exc:
        raise FfmpegInstallError("The FFmpeg download timed out. Try again with a stronger connection.") from exc
    except zipfile.BadZipFile as exc:
        raise FfmpegInstallError("The downloaded FFmpeg archive could not be opened. Please try again.") from exc
    except PermissionError as exc:
        raise FfmpegInstallError("ZDBatcher could not write to tools/ffmpeg. Check folder permissions and try again.") from exc
    except OSError as exc:
        raise FfmpegInstallError(f"FFmpeg installation failed while writing files: {exc}") from exc
    finally:
        try:
            if partial_path.exists():
                partial_path.unlink()
        except OSError:
            pass

        shutil.rmtree(temp_dir, ignore_errors=True)


def _target_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "tools" / "ffmpeg"


def _download_archive(partial_path: Path, archive_path: Path, progress: ProgressCallback | None):
    _emit(progress, "Downloading FFmpeg release essentials archive...")

    request = urllib.request.Request(
        FFMPEG_ARCHIVE_URL,
        headers={"User-Agent": "ZDBatcher FFmpeg Installer"},
    )

    try:
        with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            with partial_path.open("wb") as output:
                while True:
                    chunk = response.read(DOWNLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    output.write(chunk)
    except TimeoutError:
        raise
    except urllib.error.URLError:
        raise

    if not partial_path.is_file():
        raise FfmpegInstallError("The FFmpeg download did not create an archive file.")

    partial_path.replace(archive_path)


def _extract_tools(
    archive_path: Path,
    temp_dir: Path,
    ffmpeg_path: Path,
    ffprobe_path: Path,
    progress: ProgressCallback | None,
):
    _emit(progress, "Extracting ffmpeg.exe and ffprobe.exe...")

    with zipfile.ZipFile(archive_path) as archive:
        _extract_one(archive, "ffmpeg.exe", temp_dir, ffmpeg_path)
        _extract_one(archive, "ffprobe.exe", temp_dir, ffprobe_path)


def _extract_one(archive: zipfile.ZipFile, executable_name: str, temp_dir: Path, destination: Path):
    member_name = _find_archive_member(archive, executable_name)
    if not member_name:
        raise FfmpegInstallError(f"Could not find {executable_name} in the downloaded archive.")

    temp_path = temp_dir / executable_name
    with archive.open(member_name) as source, temp_path.open("wb") as output:
        shutil.copyfileobj(source, output)

    temp_path.replace(destination)


def _find_archive_member(archive: zipfile.ZipFile, executable_name: str) -> str | None:
    suffix = f"/bin/{executable_name}".lower()

    for name in archive.namelist():
        normalized = name.replace("\\", "/").lower()
        if normalized.endswith(suffix):
            return name

    return None


def _emit(progress: ProgressCallback | None, message: str):
    if progress:
        progress(message)
