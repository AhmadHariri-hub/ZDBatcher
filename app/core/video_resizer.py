import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.core.media_engine import find_ffmpeg, find_ffprobe
from app.core.video_converter import (
    OUTPUT_STANDARD_VIDEO_FORMATS,
    OUTPUT_VIDEO_FORMATS,
    QUALITY_BALANCED,
    QUALITY_HIGH,
    QUALITY_PRESETS,
    QUALITY_SMALL,
    SUPPORTED_VIDEO_INPUTS,
    VideoConversionError,
    _choose_webm_encoder,
    _clean_ffmpeg_error,
    get_video_files,
    is_gif_input,
    quality_crf,
)


RESIZABLE_VIDEO_OUTPUT_FORMATS = sorted(
    {format_name.lower() for format_name in OUTPUT_VIDEO_FORMATS}
    | {extension.lower().lstrip(".") for extension in SUPPORTED_VIDEO_INPUTS}
)

RESIZE_PRESET = "Preset resolution"
RESIZE_CUSTOM = "Custom width/height"
RESIZE_PERCENT = "Scale percentage"
RESIZE_NONE = "No resize, only compress"
RESIZE_MODES = [RESIZE_PRESET, RESIZE_CUSTOM, RESIZE_PERCENT, RESIZE_NONE]

PRESET_4K = "4K"
PRESET_1440 = "1440p"
PRESET_1080 = "1080p"
PRESET_720 = "720p"
PRESET_480 = "480p"
PRESET_360 = "360p"
PRESET_RESOLUTIONS = [PRESET_4K, PRESET_1440, PRESET_1080, PRESET_720, PRESET_480, PRESET_360]

PRESET_HEIGHTS = {
    PRESET_4K: 2160,
    PRESET_1440: 1440,
    PRESET_1080: 1080,
    PRESET_720: 720,
    PRESET_480: 480,
    PRESET_360: 360,
}


@dataclass(frozen=True)
class VideoResizeResult:
    output_path: Path
    approximate_target_size: bool


class VideoResizeError(VideoConversionError):
    pass


def parse_optional_target_bytes(value: str) -> int | None:
    value = value.strip()

    if not value:
        return None

    parsed = float(value)

    if parsed <= 0:
        raise ValueError("Target max file size must be greater than zero.")

    return max(1, int(parsed * 1_000_000) - 1024)


def parse_positive_int(value: str, label: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be a valid whole number.") from exc

    if parsed <= 0:
        raise ValueError(f"{label} must be greater than zero.")

    return parsed


def parse_percentage(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError("Percentage must be a valid number.") from exc

    if parsed <= 0:
        raise ValueError("Percentage must be greater than zero.")

    return parsed


def original_video_output_format(input_file: Path) -> str:
    extension = input_file.suffix.lower().lstrip(".")

    if not extension:
        raise ValueError("Source video does not have a file extension.")

    if extension not in RESIZABLE_VIDEO_OUTPUT_FORMATS:
        raise ValueError(f"Cannot resize {input_file.suffix} while preserving its original format. Use Video Converter first.")

    return extension


def resize_video(
    ffmpeg_path: str,
    input_file: Path,
    output_file: Path,
    output_format: str,
    resize_mode: str,
    preset_resolution: str,
    width: int | None,
    height: int | None,
    percentage: float | None,
    quality_preset: str,
    target_bytes: int | None,
) -> VideoResizeResult:
    output_format = output_format.lower()

    if output_format == "gif" and target_bytes is not None:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        for gif_fps, gif_scale in _gif_target_attempts():
            command = build_resize_command(
                ffmpeg_path=ffmpeg_path,
                input_file=input_file,
                output_file=output_file,
                output_format=output_format,
                resize_mode=resize_mode,
                preset_resolution=preset_resolution,
                width=width,
                height=height,
                percentage=percentage,
                quality_preset=quality_preset,
                target_bytes=None,
                gif_target_fps=gif_fps,
                gif_target_scale=gif_scale,
            )
            _run_resize_command(command, output_file)
            if output_file.stat().st_size <= target_bytes:
                break

        return VideoResizeResult(
            output_path=output_file,
            approximate_target_size=True,
        )

    command = build_resize_command(
        ffmpeg_path=ffmpeg_path,
        input_file=input_file,
        output_file=output_file,
        output_format=output_format,
        resize_mode=resize_mode,
        preset_resolution=preset_resolution,
        width=width,
        height=height,
        percentage=percentage,
        quality_preset=quality_preset,
        target_bytes=target_bytes,
    )

    output_file.parent.mkdir(parents=True, exist_ok=True)
    _run_resize_command(command, output_file)

    return VideoResizeResult(
        output_path=output_file,
        approximate_target_size=target_bytes is not None,
    )


def _run_resize_command(command: list[str], output_file: Path):
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
        raise VideoResizeError(
            _clean_ffmpeg_error(
                stderr=result.stderr,
                command=command,
                returncode=result.returncode,
            )
        )

    if not output_file.exists():
        raise VideoResizeError("Video engine finished but did not create an output file.")


def build_resize_command(
    ffmpeg_path: str,
    input_file: Path,
    output_file: Path,
    output_format: str,
    resize_mode: str,
    preset_resolution: str,
    width: int | None,
    height: int | None,
    percentage: float | None,
    quality_preset: str,
    target_bytes: int | None,
    gif_target_fps: str | None = None,
    gif_target_scale: float = 1.0,
) -> list[str]:
    output_format = output_format.lower()

    if output_format not in RESIZABLE_VIDEO_OUTPUT_FORMATS:
        raise ValueError(f"Unsupported output format: {output_format}")

    command = [ffmpeg_path, "-hide_banner", "-y"]

    if is_gif_input(input_file):
        command.extend(["-ignore_loop", "1"])

    command.extend([
        "-i", str(input_file),
    ])

    if output_format == "gif":
        command.extend(_gif_resize_settings(
            resize_mode=resize_mode,
            preset_resolution=preset_resolution,
            width=width,
            height=height,
            percentage=percentage,
            target_fps=gif_target_fps,
            target_scale=gif_target_scale,
        ))
        command.append(str(output_file))
        return command

    command.extend([
        "-map", "0:v:0",
        "-map", "0:a?",
        "-sn",
    ])

    filters = _resize_filters(
        output_format=output_format,
        resize_mode=resize_mode,
        preset_resolution=preset_resolution,
        width=width,
        height=height,
        percentage=percentage,
    )

    if filters:
        command.extend(["-vf", ",".join(filters)])

    if target_bytes is None:
        command.extend(_crf_settings(ffmpeg_path, output_format, quality_preset, input_file))
    else:
        duration = get_duration_seconds(input_file)

        if duration is None or duration <= 0:
            raise VideoResizeError("Could not read video duration for target-size bitrate estimate.")

        command.extend(_target_size_settings(ffmpeg_path, output_format, quality_preset, input_file, duration, target_bytes))

    command.append(str(output_file))
    return command


def _gif_target_attempts() -> list[tuple[str | None, float]]:
    return [
        (None, 1.0),
        ("20", 0.9),
        ("15", 0.8),
        ("10", 0.7),
        ("8", 0.6),
        ("5", 0.5),
    ]


def _gif_resize_settings(
    resize_mode: str,
    preset_resolution: str,
    width: int | None,
    height: int | None,
    percentage: float | None,
    target_fps: str | None,
    target_scale: float,
) -> list[str]:
    filters = _resize_filters(
        output_format="gif",
        resize_mode=resize_mode,
        preset_resolution=preset_resolution,
        width=width,
        height=height,
        percentage=percentage,
    )

    if target_fps:
        filters.insert(0, f"fps={target_fps}")

    if target_scale < 1.0:
        filters.append(f"scale=trunc(iw*{target_scale}/2)*2:trunc(ih*{target_scale}/2)*2:flags=lanczos")

    filter_chain = ",".join(filters)
    filter_complex = (
        f"[0:v]{filter_chain},split[gif_a][gif_b];"
        "[gif_a]palettegen=stats_mode=full[gif_palette];"
        "[gif_b][gif_palette]paletteuse=dither=sierra2_4a[gif_out]"
    )

    return [
        "-filter_complex", filter_complex,
        "-map", "[gif_out]",
        "-an",
        "-sn",
        "-loop", "0",
    ]


def get_duration_seconds(input_file: Path) -> float | None:
    ffprobe_path = find_ffprobe()

    if not ffprobe_path:
        return None

    result = subprocess.run(
        [
            ffprobe_path,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            str(input_file),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )

    if result.returncode != 0:
        return None

    try:
        data = json.loads(result.stdout or "{}")
        return float(data.get("format", {}).get("duration", 0))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _resize_filters(
    output_format: str,
    resize_mode: str,
    preset_resolution: str,
    width: int | None,
    height: int | None,
    percentage: float | None,
) -> list[str]:
    filters = []

    if resize_mode == RESIZE_PRESET:
        preset_height = PRESET_HEIGHTS.get(preset_resolution)

        if not preset_height:
            raise ValueError("Choose a valid preset resolution.")

        filters.append(f"scale=-2:{preset_height}:flags=lanczos")

    elif resize_mode == RESIZE_CUSTOM:
        if not width or not height:
            raise ValueError("Width and height are required for custom resizing.")

        filters.append(f"scale=trunc({width}/2)*2:trunc({height}/2)*2:flags=lanczos")

    elif resize_mode == RESIZE_PERCENT:
        if not percentage:
            raise ValueError("Percentage is required for percentage scaling.")

        scale = percentage / 100
        filters.append(f"scale=trunc(iw*{scale}/2)*2:trunc(ih*{scale}/2)*2:flags=lanczos")

    elif resize_mode == RESIZE_NONE:
        filters.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")

    else:
        raise ValueError(f"Unknown resize mode: {resize_mode}")

    if output_format in {"mp4", "mov", "mkv"}:
        filters.append("format=yuv420p")

    return filters


def _crf_settings(
    ffmpeg_path: str,
    output_format: str,
    quality_preset: str,
    input_file: Path,
) -> list[str]:
    crf = str(quality_crf(output_format, quality_preset))

    if output_format == "webm":
        encoder = _choose_webm_encoder(ffmpeg_path)
        pixel_format = "yuva420p" if is_gif_input(input_file) else "yuv420p"

        settings = [
            "-c:v", encoder,
            "-crf", crf,
            "-b:v", "0",
            "-pix_fmt", pixel_format,
            "-c:a", "libopus",
            "-b:a", "128k",
        ]

        if encoder == "libvpx-vp9":
            settings.extend(["-deadline", "good", "-cpu-used", "2"])

        return settings

    settings = [
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", crf,
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "160k",
    ]

    if output_format in {"mp4", "mov"}:
        settings.extend(["-movflags", "+faststart"])

    return settings


def _target_size_settings(
    ffmpeg_path: str,
    output_format: str,
    quality_preset: str,
    input_file: Path,
    duration_seconds: float,
    target_bytes: int,
) -> list[str]:
    audio_kbps = {
        QUALITY_HIGH: 160,
        QUALITY_BALANCED: 128,
        QUALITY_SMALL: 96,
    }.get(quality_preset, 128)
    total_kbps = max(150, int((target_bytes * 8 / duration_seconds / 1000) * 0.92))
    video_kbps = max(100, total_kbps - audio_kbps)

    if output_format == "webm":
        encoder = _choose_webm_encoder(ffmpeg_path)
        pixel_format = "yuva420p" if is_gif_input(input_file) else "yuv420p"

        settings = [
            "-c:v", encoder,
            "-b:v", f"{video_kbps}k",
            "-maxrate", f"{video_kbps}k",
            "-bufsize", f"{video_kbps * 2}k",
            "-pix_fmt", pixel_format,
            "-c:a", "libopus",
            "-b:a", f"{audio_kbps}k",
        ]

        if encoder == "libvpx-vp9":
            settings.extend(["-deadline", "good", "-cpu-used", "2"])

        return settings

    settings = [
        "-c:v", "libx264",
        "-preset", "medium",
        "-b:v", f"{video_kbps}k",
        "-maxrate", f"{video_kbps}k",
        "-bufsize", f"{video_kbps * 2}k",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", f"{audio_kbps}k",
    ]

    if output_format in {"mp4", "mov"}:
        settings.extend(["-movflags", "+faststart"])

    return settings
