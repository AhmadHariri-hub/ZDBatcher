import shutil
import sys
from functools import lru_cache
from pathlib import Path


FFMPEG_RELATIVE_PATHS = (
    Path("tools") / "ffmpeg" / "ffmpeg.exe",
    Path("bin") / "ffmpeg.exe",
    Path("ffmpeg.exe"),
)


@lru_cache(maxsize=1)
def find_ffmpeg() -> str | None:
    bundled = _find_bundled_executable("ffmpeg.exe", FFMPEG_RELATIVE_PATHS)

    if bundled:
        return bundled

    if _is_frozen():
        return None

    return shutil.which("ffmpeg")


@lru_cache(maxsize=1)
def find_ffprobe() -> str | None:
    ffmpeg_path = find_ffmpeg()

    if ffmpeg_path:
        adjacent = Path(ffmpeg_path).with_name("ffprobe.exe")

        if adjacent.is_file():
            return str(adjacent)

    if _is_frozen():
        return None

    return shutil.which("ffprobe")


def _find_bundled_executable(name: str, relative_paths: tuple[Path, ...]) -> str | None:
    for base in _bundle_roots():
        for relative_path in relative_paths:
            candidate = base / relative_path

            if candidate.name.lower() != name.lower():
                continue

            if candidate.is_file():
                return str(candidate)

    return None


def _bundle_roots() -> list[Path]:
    if _is_frozen():
        roots = []
        meipass = getattr(sys, "_MEIPASS", None)

        if meipass:
            roots.append(Path(meipass))

        roots.append(Path(sys.executable).resolve().parent)
        return roots

    return [Path(__file__).resolve().parents[2]]


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))
