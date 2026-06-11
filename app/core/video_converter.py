import subprocess
from functools import lru_cache
from pathlib import Path

from app.core.file_utils import is_inside_folder, natural_sort_key
from app.core.media_engine import find_ffmpeg


SUPPORTED_VIDEO_INPUTS = {
    ".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v",
    ".flv", ".wmv", ".mpg", ".mpeg", ".3gp", ".ts", ".gif",
}

OUTPUT_STANDARD_VIDEO_FORMATS = ["mp4", "webm", "mkv", "mov"]
OUTPUT_VIDEO_FORMATS = [*OUTPUT_STANDARD_VIDEO_FORMATS, "gif"]

QUALITY_HIGH = "High quality"
QUALITY_BALANCED = "Balanced"
QUALITY_SMALL = "Small size"
QUALITY_PRESETS = [QUALITY_HIGH, QUALITY_BALANCED, QUALITY_SMALL]

RESIZE_KEEP = "Keep original"
RESIZE_1080 = "1080p"
RESIZE_720 = "720p"
RESIZE_480 = "480p"
RESIZE_OPTIONS = [RESIZE_KEEP, RESIZE_1080, RESIZE_720, RESIZE_480]

GIF_FPS_ORIGINAL = "Original"
GIF_FPS_OPTIONS = [GIF_FPS_ORIGINAL, "30", "20", "15", "10", "5"]

GIF_WIDTH_KEEP = "Keep original"
GIF_WIDTH_1080 = "1080"
GIF_WIDTH_720 = "720"
GIF_WIDTH_480 = "480"
GIF_WIDTH_CUSTOM = "custom"
GIF_WIDTH_OPTIONS = [
    GIF_WIDTH_KEEP,
    GIF_WIDTH_1080,
    GIF_WIDTH_720,
    GIF_WIDTH_480,
    GIF_WIDTH_CUSTOM,
]


class VideoConversionError(RuntimeError):
    pass


def is_ffmpeg_available() -> bool:
    return find_ffmpeg() is not None


def get_video_files(
    input_dir: Path,
    include_subfolders: bool,
    output_dir: Path | None = None,
) -> list[Path]:
    paths = input_dir.rglob("*") if include_subfolders else input_dir.iterdir()

    files = [
        path for path in paths
        if path.is_file() and path.suffix.lower() in SUPPORTED_VIDEO_INPUTS
    ]

    if output_dir is not None and output_dir.exists():
        files = [
            file for file in files
            if not is_inside_folder(file, output_dir)
        ]

    return sorted(files, key=natural_sort_key)


def is_gif_input(path: Path) -> bool:
    return path.suffix.lower() == ".gif"


def build_ffmpeg_command(
    ffmpeg_path: str,
    input_file: Path,
    output_file: Path,
    output_format: str,
    quality_preset: str,
    resize_option: str,
    gif_fps: str = GIF_FPS_ORIGINAL,
    gif_width_option: str = GIF_WIDTH_KEEP,
    gif_custom_width: int | None = None,
) -> list[str]:
    output_format = output_format.lower()

    if output_format not in OUTPUT_VIDEO_FORMATS:
        raise ValueError(f"Unsupported output format: {output_format}")

    command = [ffmpeg_path, "-hide_banner", "-y"]

    if is_gif_input(input_file):
        command.extend(["-ignore_loop", "1"])

    command.extend(["-i", str(input_file)])

    if output_format == "gif":
        command.extend(_gif_output_settings(gif_fps, gif_width_option, gif_custom_width))
        command.append(str(output_file))
        return command

    command.extend(["-map", "0:v:0", "-map", "0:a?", "-sn"])

    filters = _video_filters(output_format, resize_option)

    if filters:
        command.extend(["-vf", ",".join(filters)])

    command.extend(_format_settings(ffmpeg_path, output_format, quality_preset, input_file))
    command.append(str(output_file))

    return command


def convert_video(
    ffmpeg_path: str,
    input_file: Path,
    output_file: Path,
    output_format: str,
    quality_preset: str,
    resize_option: str,
    gif_fps: str = GIF_FPS_ORIGINAL,
    gif_width_option: str = GIF_WIDTH_KEEP,
    gif_custom_width: int | None = None,
) -> Path:
    command = build_ffmpeg_command(
        ffmpeg_path=ffmpeg_path,
        input_file=input_file,
        output_file=output_file,
        output_format=output_format,
        quality_preset=quality_preset,
        resize_option=resize_option,
        gif_fps=gif_fps,
        gif_width_option=gif_width_option,
        gif_custom_width=gif_custom_width,
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
        raise VideoConversionError(
            _clean_ffmpeg_error(
                stderr=result.stderr,
                command=command,
                returncode=result.returncode,
            )
        )

    if not output_file.exists():
        raise VideoConversionError("FFmpeg finished but did not create an output file.")

    return output_file


def quality_crf(output_format: str, quality_preset: str) -> int:
    output_format = output_format.lower()

    if output_format == "webm":
        return {
            QUALITY_HIGH: 24,
            QUALITY_BALANCED: 32,
            QUALITY_SMALL: 40,
        }.get(quality_preset, 32)

    return {
        QUALITY_HIGH: 18,
        QUALITY_BALANCED: 23,
        QUALITY_SMALL: 28,
    }.get(quality_preset, 23)


def _video_filters(output_format: str, resize_option: str) -> list[str]:
    filters = []

    resize_heights = {
        RESIZE_1080: 1080,
        RESIZE_720: 720,
        RESIZE_480: 480,
    }
    height = resize_heights.get(resize_option)

    if height:
        filters.append(f"scale=-2:{height}:flags=lanczos")
    else:
        # H.264/MP4/MOV can fail with odd GIF/video dimensions.
        # This keeps the size almost unchanged but forces even width/height.
        filters.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")

    if output_format in {"mp4", "mov", "mkv"}:
        filters.append("format=yuv420p")

    return filters


def _gif_output_settings(
    fps_option: str,
    width_option: str,
    custom_width: int | None,
) -> list[str]:
    filters = _gif_palette_filters(fps_option, width_option, custom_width)
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


def _gif_palette_filters(
    fps_option: str,
    width_option: str,
    custom_width: int | None,
) -> list[str]:
    filters = []

    if fps_option != GIF_FPS_ORIGINAL:
        if fps_option not in GIF_FPS_OPTIONS:
            raise ValueError("Choose a valid GIF FPS option.")

        filters.append(f"fps={fps_option}")

    width = _gif_width(width_option, custom_width)

    if width:
        filters.append(f"scale={width}:-1:flags=lanczos")

    return filters or ["setpts=PTS"]


def _gif_width(width_option: str, custom_width: int | None) -> int | None:
    if width_option == GIF_WIDTH_KEEP:
        return None

    if width_option == GIF_WIDTH_CUSTOM:
        if not custom_width:
            raise ValueError("Custom GIF width is required.")

        if custom_width <= 0:
            raise ValueError("Custom GIF width must be greater than zero.")

        return custom_width

    if width_option not in GIF_WIDTH_OPTIONS:
        raise ValueError("Choose a valid GIF width option.")

    return int(width_option)


def _format_settings(
    ffmpeg_path: str,
    output_format: str,
    quality_preset: str,
    input_file: Path,
) -> list[str]:
    crf = str(quality_crf(output_format, quality_preset))

    if output_format == "webm":
        video_encoder = _choose_webm_encoder(ffmpeg_path)
        pixel_format = "yuva420p" if is_gif_input(input_file) else "yuv420p"

        if video_encoder == "libvpx-vp9":
            return [
                "-c:v", "libvpx-vp9",
                "-crf", crf,
                "-b:v", "0",
                "-deadline", "good",
                "-cpu-used", "2",
                "-pix_fmt", pixel_format,
                "-c:a", "libopus",
                "-b:a", "128k",
            ]

        return [
            "-c:v", "libvpx",
            "-crf", crf,
            "-b:v", "0",
            "-pix_fmt", pixel_format,
            "-c:a", "libopus",
            "-b:a", "128k",
        ]

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


def _choose_webm_encoder(ffmpeg_path: str) -> str:
    encoders = _available_encoders(ffmpeg_path)

    if "libvpx-vp9" in encoders:
        return "libvpx-vp9"

    if "libvpx" in encoders:
        return "libvpx"

    return "libvpx-vp9"


@lru_cache(maxsize=4)
def _available_encoders(ffmpeg_path: str) -> set[str]:
    try:
        result = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-encoders"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )
    except OSError:
        return set()

    output = f"{result.stdout}\n{result.stderr}"
    encoders = set()

    for line in output.splitlines():
        parts = line.split()

        if len(parts) >= 2:
            encoders.add(parts[1])

    return encoders


def _clean_ffmpeg_error(
    stderr: str,
    command: list[str] | None = None,
    returncode: int | None = None,
) -> str:
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    parts = []

    if returncode is not None:
        parts.append(f"FFmpeg return code: {returncode}")

    if command:
        parts.append("Command:")
        parts.append(
            " ".join(
                f'"{part}"' if " " in str(part) else str(part)
                for part in _redact_ffmpeg_command(command)
            )
        )

    if not lines:
        parts.append("FFmpeg failed without an error message.")
        return "\n".join(parts)

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
            or "height not divisible" in lower
            or "width not divisible" in lower
            or "incorrect codec parameters" in lower
        ):
            important.append(line)

    parts.append("FFmpeg error:")

    if important:
        parts.extend(important[-8:])
    else:
        parts.extend(lines[-14:])

    return "\n".join(parts)


def _redact_ffmpeg_command(command: list[str]) -> list[str]:
    if not command:
        return command

    return ["ffmpeg", *command[1:]]
