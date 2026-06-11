from pathlib import Path

from app.config import SUPPORTED_INPUTS
from app.core.audio_converter import (
    AUDIO_INPUT_EXTENSIONS,
    FILTER_AUDIO_AND_VIDEO,
    FILTER_AUDIO_ONLY,
    FILTER_VIDEO_ONLY,
    VIDEO_AUDIO_INPUT_EXTENSIONS,
    convert_audio,
    input_filter_includes_video,
)
from app.core.file_utils import is_inside_folder, natural_sort_key
from app.core.image_converter import convert_image, original_output_format
from app.core.image_resizer import resize_and_compress_image
from app.core.video_converter import (
    GIF_FPS_ORIGINAL,
    GIF_WIDTH_KEEP,
    QUALITY_BALANCED as VIDEO_QUALITY_BALANCED,
    RESIZE_KEEP,
    SUPPORTED_VIDEO_INPUTS,
    convert_video,
    is_gif_input,
)
from app.core.video_resizer import original_video_output_format, resize_video


MEDIA_IMAGE = "image"
MEDIA_VIDEO = "video"
MEDIA_AUDIO = "audio"

MEDIA_LABELS = {
    MEDIA_IMAGE: "Image",
    MEDIA_VIDEO: "Video",
    MEDIA_AUDIO: "Audio",
}

MEDIA_FOLDER_NAMES = {
    MEDIA_IMAGE: "Images",
    MEDIA_VIDEO: "Videos",
    MEDIA_AUDIO: "Audio",
}

ORG_ONE_FOLDER = "Keep everything in one output folder"
ORG_MEDIA_FOLDERS = "Create media-type folders"
OUTPUT_ORGANIZATION_OPTIONS = [ORG_ONE_FOLDER, ORG_MEDIA_FOLDERS]


def classify_media_file(path: Path) -> str | None:
    suffix = path.suffix.lower()

    if suffix == ".gif":
        return MEDIA_VIDEO

    if suffix in SUPPORTED_VIDEO_INPUTS:
        return MEDIA_VIDEO

    if suffix in AUDIO_INPUT_EXTENSIONS or suffix in VIDEO_AUDIO_INPUT_EXTENSIONS:
        return MEDIA_AUDIO

    if suffix in SUPPORTED_INPUTS:
        return MEDIA_IMAGE

    return None


def collect_media_files(
    input_dir: Path,
    include_subfolders: bool,
    enabled_media: set[str],
    output_dir: Path | None = None,
    audio_input_filter: str | None = None,
) -> list[tuple[Path, str]]:
    paths = input_dir.rglob("*") if include_subfolders else input_dir.iterdir()
    files = []

    for path in paths:
        if not path.is_file():
            continue

        media_type = classify_media_file_for_conversion(path, enabled_media, audio_input_filter)

        if media_type is None or media_type not in enabled_media:
            continue

        if output_dir is not None and output_dir.exists() and is_inside_folder(path, output_dir):
            continue

        files.append((path, media_type))

    return sorted(files, key=lambda item: (item[1], natural_sort_key(item[0])))


def classify_media_file_for_conversion(
    path: Path,
    enabled_media: set[str],
    audio_input_filter: str | None = None,
) -> str | None:
    if audio_input_filter is None:
        return classify_media_file(path)

    suffix = path.suffix.lower()

    if suffix in SUPPORTED_INPUTS and MEDIA_IMAGE in enabled_media:
        return MEDIA_IMAGE

    if suffix in AUDIO_INPUT_EXTENSIONS and MEDIA_AUDIO in enabled_media and audio_input_filter in {FILTER_AUDIO_ONLY, FILTER_AUDIO_AND_VIDEO}:
        return MEDIA_AUDIO

    if suffix in SUPPORTED_VIDEO_INPUTS:
        if MEDIA_VIDEO in enabled_media:
            return MEDIA_VIDEO

        if MEDIA_AUDIO in enabled_media and suffix in VIDEO_AUDIO_INPUT_EXTENSIONS and input_filter_includes_video(audio_input_filter):
            return MEDIA_AUDIO

    if suffix in VIDEO_AUDIO_INPUT_EXTENSIONS and MEDIA_AUDIO in enabled_media and audio_input_filter == FILTER_VIDEO_ONLY:
        return MEDIA_AUDIO

    return None


def media_output_extension(media_type: str, image_format: str, video_format: str, audio_format: str) -> str:
    if media_type == MEDIA_IMAGE:
        return image_format.lower().lstrip(".")

    if media_type == MEDIA_VIDEO:
        return video_format.lower().lstrip(".")

    if media_type == MEDIA_AUDIO:
        return audio_format.lower().lstrip(".")

    raise ValueError(f"Unsupported media type: {media_type}")


def media_original_output_extension(media_type: str, source_file: Path) -> str:
    if media_type == MEDIA_IMAGE:
        return original_output_format(source_file)

    if media_type == MEDIA_VIDEO:
        return original_video_output_format(source_file)

    raise ValueError(f"Unsupported resizable media type: {media_type}")


def convert_mixed_file(
    source_file: Path,
    media_type: str,
    output_file: Path,
    *,
    image_format: str,
    ffmpeg_path: str | None,
    video_format: str,
    audio_format: str,
    audio_quality: str,
    video_quality: str = VIDEO_QUALITY_BALANCED,
    gif_fps: str = GIF_FPS_ORIGINAL,
    gif_width_option: str = GIF_WIDTH_KEEP,
    gif_custom_width: int | None = None,
) -> Path:
    if media_type == MEDIA_IMAGE:
        convert_image(source_file, output_file, image_format)
        return output_file

    if media_type == MEDIA_VIDEO:
        if not ffmpeg_path:
            raise RuntimeError("Media conversion unavailable. Required components are missing.")

        return convert_video(
            ffmpeg_path=ffmpeg_path,
            input_file=source_file,
            output_file=output_file,
            output_format=video_format,
            quality_preset=video_quality,
            resize_option=RESIZE_KEEP,
            gif_fps=gif_fps,
            gif_width_option=gif_width_option,
            gif_custom_width=gif_custom_width,
        )

    if media_type == MEDIA_AUDIO:
        if not ffmpeg_path:
            raise RuntimeError("Media conversion unavailable. Required components are missing.")

        return convert_audio(
            ffmpeg_path=ffmpeg_path,
            input_file=source_file,
            output_file=output_file,
            output_format=audio_format,
            quality_preset=audio_quality,
        )

    raise ValueError(f"Unsupported media type: {media_type}")


def resize_mixed_file(
    source_file: Path,
    media_type: str,
    output_file: Path,
    *,
    ffmpeg_path: str | None,
    image_resize_mode: str,
    image_width: int | None,
    image_height: int | None,
    image_percentage: float | None,
    image_quality: str,
    image_max_bytes: int | None,
    video_resize_mode: str,
    video_preset_resolution: str,
    video_width: int | None,
    video_height: int | None,
    video_percentage: float | None,
    video_quality: str,
    video_target_bytes: int | None,
) -> Path:
    if media_type == MEDIA_IMAGE:
        output_format = original_output_format(source_file)
        resize_and_compress_image(
            input_path=source_file,
            output_path=output_file,
            out_format=output_format,
            resize_mode=image_resize_mode,
            width=image_width,
            height=image_height,
            percentage=image_percentage,
            quality_preset=image_quality,
            max_bytes=image_max_bytes,
        )
        return output_file

    if media_type == MEDIA_VIDEO:
        if not ffmpeg_path:
            raise RuntimeError("Media resizing unavailable. Required components are missing.")

        output_format = original_video_output_format(source_file)
        resize_video(
            ffmpeg_path=ffmpeg_path,
            input_file=source_file,
            output_file=output_file,
            output_format=output_format,
            resize_mode=video_resize_mode,
            preset_resolution=video_preset_resolution,
            width=video_width,
            height=video_height,
            percentage=video_percentage,
            quality_preset=video_quality,
            target_bytes=video_target_bytes,
        )
        return output_file

    raise ValueError(f"Unsupported resizable media type: {media_type}")


def is_animated_media(path: Path) -> bool:
    return is_gif_input(path)
