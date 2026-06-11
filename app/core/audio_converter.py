import subprocess
from pathlib import Path

from app.core.file_utils import is_inside_folder, natural_sort_key
from app.core.media_engine import find_ffmpeg


AUDIO_INPUT_EXTENSIONS = {
    ".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg",
    ".opus", ".wma", ".amr", ".aiff", ".aif", ".caf",
}

VIDEO_AUDIO_INPUT_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".flv", ".wmv",
}

SUPPORTED_AUDIO_INPUTS = AUDIO_INPUT_EXTENSIONS | VIDEO_AUDIO_INPUT_EXTENSIONS

OUTPUT_AUDIO_FORMATS = ["mp3", "wav", "flac", "m4a", "ogg", "opus"]

FILTER_AUDIO_ONLY = "Audio files only"
FILTER_VIDEO_ONLY = "Videos with audio only"
FILTER_AUDIO_AND_VIDEO = "Audio + videos"
INPUT_TYPE_FILTERS = [FILTER_AUDIO_ONLY, FILTER_VIDEO_ONLY, FILTER_AUDIO_AND_VIDEO]

QUALITY_HIGH = "High quality"
QUALITY_BALANCED = "Balanced"
QUALITY_SMALL = "Small size"
QUALITY_PRESETS = [QUALITY_HIGH, QUALITY_BALANCED, QUALITY_SMALL]


class AudioConversionError(RuntimeError):
    pass


def is_audio_engine_available() -> bool:
    return find_ffmpeg() is not None


def input_filter_includes_video(input_filter: str) -> bool:
    return input_filter in {FILTER_VIDEO_ONLY, FILTER_AUDIO_AND_VIDEO}


def is_video_audio_input(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_AUDIO_INPUT_EXTENSIONS


def get_audio_inputs(
    input_dir: Path,
    include_subfolders: bool,
    input_filter: str,
    output_dir: Path | None = None,
) -> list[Path]:
    if input_filter == FILTER_AUDIO_ONLY:
        extensions = AUDIO_INPUT_EXTENSIONS
    elif input_filter == FILTER_VIDEO_ONLY:
        extensions = VIDEO_AUDIO_INPUT_EXTENSIONS
    else:
        extensions = SUPPORTED_AUDIO_INPUTS

    paths = input_dir.rglob("*") if include_subfolders else input_dir.iterdir()
    files = [
        path for path in paths
        if path.is_file() and path.suffix.lower() in extensions
    ]

    if output_dir is not None and output_dir.exists():
        files = [
            file for file in files
            if not is_inside_folder(file, output_dir)
        ]

    return sorted(files, key=natural_sort_key)


def build_ffmpeg_command(
    ffmpeg_path: str,
    input_file: Path,
    output_file: Path,
    output_format: str,
    quality_preset: str,
) -> list[str]:
    output_format = output_format.lower()

    if output_format not in OUTPUT_AUDIO_FORMATS:
        raise ValueError(f"Unsupported output format: {output_format}")

    command = [
        ffmpeg_path,
        "-hide_banner",
        "-y",
        "-i",
        str(input_file),
        "-map",
        "0:a:0",
        "-vn",
        "-sn",
    ]
    command.extend(_format_settings(output_format, quality_preset))
    command.append(str(output_file))
    return command


def convert_audio(
    ffmpeg_path: str,
    input_file: Path,
    output_file: Path,
    output_format: str,
    quality_preset: str,
) -> Path:
    command = build_ffmpeg_command(
        ffmpeg_path=ffmpeg_path,
        input_file=input_file,
        output_file=output_file,
        output_format=output_format,
        quality_preset=quality_preset,
    )

    output_file.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )

    if result.returncode != 0:
        raise AudioConversionError(_clean_ffmpeg_error(result.stderr))

    if not output_file.exists():
        raise AudioConversionError("The audio engine finished but did not create an output file.")

    return output_file


def describe_quality(output_format: str, quality_preset: str) -> str:
    output_format = output_format.lower()

    if output_format == "flac":
        return "Lossless"

    if output_format == "wav":
        return "Uncompressed"

    settings = {
        "mp3": {
            QUALITY_HIGH: "192k",
            QUALITY_BALANCED: "160k",
            QUALITY_SMALL: "96k",
        },
        "m4a": {
            QUALITY_HIGH: "192k",
            QUALITY_BALANCED: "160k",
            QUALITY_SMALL: "96k",
        },
        "ogg": {
            QUALITY_HIGH: "quality 6",
            QUALITY_BALANCED: "quality 4",
            QUALITY_SMALL: "quality 2",
        },
        "opus": {
            QUALITY_HIGH: "160k",
            QUALITY_BALANCED: "96k",
            QUALITY_SMALL: "64k",
        },
    }

    return settings.get(output_format, {}).get(quality_preset, "")


def _format_settings(output_format: str, quality_preset: str) -> list[str]:
    if output_format == "mp3":
        return ["-c:a", "libmp3lame", "-b:a", _bitrate("mp3", quality_preset)]

    if output_format == "m4a":
        return ["-c:a", "aac", "-b:a", _bitrate("m4a", quality_preset)]

    if output_format == "ogg":
        return ["-c:a", "libvorbis", "-q:a", _ogg_quality(quality_preset)]

    if output_format == "opus":
        return ["-c:a", "libopus", "-b:a", _bitrate("opus", quality_preset)]

    if output_format == "flac":
        return ["-c:a", "flac"]

    if output_format == "wav":
        return ["-c:a", "pcm_s16le"]

    raise ValueError(f"Unsupported output format: {output_format}")


def _bitrate(output_format: str, quality_preset: str) -> str:
    bitrates = {
        "mp3": {
            QUALITY_HIGH: "192k",
            QUALITY_BALANCED: "160k",
            QUALITY_SMALL: "96k",
        },
        "m4a": {
            QUALITY_HIGH: "192k",
            QUALITY_BALANCED: "160k",
            QUALITY_SMALL: "96k",
        },
        "opus": {
            QUALITY_HIGH: "160k",
            QUALITY_BALANCED: "96k",
            QUALITY_SMALL: "64k",
        },
    }

    return bitrates[output_format].get(quality_preset, bitrates[output_format][QUALITY_BALANCED])


def _ogg_quality(quality_preset: str) -> str:
    qualities = {
        QUALITY_HIGH: "6",
        QUALITY_BALANCED: "4",
        QUALITY_SMALL: "2",
    }
    return qualities.get(quality_preset, "4")


def _clean_ffmpeg_error(stderr: str) -> str:
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]

    if not lines:
        return "Audio conversion failed without an error message."

    important = []

    for line in lines:
        lower = line.lower()

        if (
            "error" in lower
            or "invalid" in lower
            or "unknown" in lower
            or "not found" in lower
            or "failed" in lower
            or "could not" in lower
            or "matches no streams" in lower
            or "stream map" in lower
        ):
            important.append(line)

    if important:
        return important[-1]

    return lines[-1]
