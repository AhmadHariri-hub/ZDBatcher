import shutil
import stat
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


FFMPEG_ARCHIVE_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
DOWNLOAD_TIMEOUT_SECONDS = 30
DOWNLOAD_CHUNK_SIZE = 1024 * 256


class FfmpegInstallError(RuntimeError):
    pass


@dataclass(frozen=True)
class InstallProgress:
    message: str
    percent: int | None = None
    downloaded_bytes: int = 0
    total_bytes: int | None = None
    indeterminate: bool = True


ProgressCallback = Callable[[InstallProgress], None]


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
    installed_paths = None

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        _download_archive(partial_path, archive_path, progress)
        _extract_tools(archive_path, temp_dir, ffmpeg_path, ffprobe_path, progress)

        if not ffmpeg_path.is_file():
            raise FfmpegInstallError("ffmpeg.exe was not installed.")

        if not ffprobe_path.is_file():
            raise FfmpegInstallError("ffprobe.exe was not installed.")

        installed_paths = (ffmpeg_path, ffprobe_path)
    except FfmpegInstallError:
        raise
    except urllib.error.URLError as exc:
        raise FfmpegInstallError("FFmpeg install failed: network error or download interrupted.") from exc
    except TimeoutError as exc:
        raise FfmpegInstallError("FFmpeg install failed: the download timed out.") from exc
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

        _emit(progress, "Cleaning temporary files...")
        _cleanup_temp_dir(temp_dir)

    _emit(progress, "FFmpeg installed successfully.", percent=100, indeterminate=False)
    return installed_paths


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
            total_bytes = _content_length(response)
            downloaded_bytes = 0
            last_percent = -1
            last_mb = -1

            with partial_path.open("wb") as output:
                while True:
                    chunk = response.read(DOWNLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    output.write(chunk)
                    downloaded_bytes += len(chunk)
                    percent = None

                    if total_bytes:
                        percent = min(100, int(downloaded_bytes * 100 / total_bytes))
                        if percent == last_percent:
                            continue

                        last_percent = percent
                    else:
                        downloaded_mb = downloaded_bytes // (1024 * 1024)
                        if downloaded_mb == last_mb:
                            continue

                        last_mb = downloaded_mb

                    _emit(
                        progress,
                        "Downloading FFmpeg",
                        percent=percent,
                        downloaded_bytes=downloaded_bytes,
                        total_bytes=total_bytes,
                        indeterminate=total_bytes is None,
                    )
    except TimeoutError:
        raise
    except urllib.error.URLError:
        raise

    if not partial_path.is_file():
        raise FfmpegInstallError("The FFmpeg download did not create an archive file.")

    _emit(progress, "Download complete. Extracting FFmpeg...", percent=100, indeterminate=False)
    partial_path.replace(archive_path)


def _extract_tools(
    archive_path: Path,
    temp_dir: Path,
    ffmpeg_path: Path,
    ffprobe_path: Path,
    progress: ProgressCallback | None,
):
    _emit(progress, "Installing ffmpeg.exe and ffprobe.exe...", percent=100, indeterminate=False)

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


def _content_length(response) -> int | None:
    value = response.headers.get("Content-Length")

    if not value:
        return None

    try:
        parsed = int(value)
    except ValueError:
        return None

    return parsed if parsed > 0 else None


def _cleanup_temp_dir(temp_dir: Path):
    for _attempt in range(5):
        try:
            shutil.rmtree(temp_dir, onerror=_make_writable)
            return
        except FileNotFoundError:
            return
        except PermissionError:
            time.sleep(0.2)
        except OSError:
            time.sleep(0.2)

    shutil.rmtree(temp_dir, ignore_errors=True)


def _make_writable(function, path, _exc_info):
    try:
        Path(path).chmod(stat.S_IWRITE)
    except OSError:
        pass

    function(path)


def _emit(
    progress: ProgressCallback | None,
    message: str,
    *,
    percent: int | None = None,
    downloaded_bytes: int = 0,
    total_bytes: int | None = None,
    indeterminate: bool = True,
):
    if progress:
        progress(
            InstallProgress(
                message=message,
                percent=percent,
                downloaded_bytes=downloaded_bytes,
                total_bytes=total_bytes,
                indeterminate=indeterminate,
            )
        )
