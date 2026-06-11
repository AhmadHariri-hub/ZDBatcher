from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from app.config import LOSSY_FORMATS
from app.core.image_converter import (
    normalize_output_format,
    open_image,
    prepare_image,
    resize_image,
    safe_max_bytes,
    save_image_to_bytes,
)


RESIZE_BY_WIDTH = "Keep aspect ratio by width"
RESIZE_BY_HEIGHT = "Keep aspect ratio by height"
RESIZE_EXACT = "Exact width and height"
RESIZE_PERCENT = "Percentage scale"
RESIZE_NONE = "No resize, only compress"
RESIZE_MODES = [
    RESIZE_BY_WIDTH,
    RESIZE_BY_HEIGHT,
    RESIZE_EXACT,
    RESIZE_PERCENT,
    RESIZE_NONE,
]

QUALITY_HIGH = "High quality"
QUALITY_BALANCED = "Balanced"
QUALITY_SMALL = "Small size"
QUALITY_PRESETS = [QUALITY_HIGH, QUALITY_BALANCED, QUALITY_SMALL]


@dataclass(frozen=True)
class ImageResizeResult:
    output_path: Path
    original_size: int
    output_size: int
    original_dimensions: tuple[int, int]
    output_dimensions: tuple[int, int]


def quality_value(preset: str) -> int:
    return {
        QUALITY_HIGH: 95,
        QUALITY_BALANCED: 85,
        QUALITY_SMALL: 72,
    }.get(preset, 85)


def parse_optional_max_bytes(value: str) -> int | None:
    value = value.strip()

    if not value:
        return None

    return safe_max_bytes(value)


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


def resize_and_compress_image(
    input_path: Path,
    output_path: Path,
    out_format: str,
    resize_mode: str,
    width: int | None,
    height: int | None,
    percentage: float | None,
    quality_preset: str,
    max_bytes: int | None,
) -> ImageResizeResult:
    out_format = normalize_output_format(out_format)
    original_size = input_path.stat().st_size
    img = open_image(input_path)
    original_dimensions = img.size

    img = apply_resize(
        img=img,
        resize_mode=resize_mode,
        width=width,
        height=height,
        percentage=percentage,
    )
    img = prepare_image(img, out_format)

    data = _encode_to_limit(
        img=img,
        out_format=out_format,
        quality=quality_value(quality_preset),
        max_bytes=max_bytes,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)

    return ImageResizeResult(
        output_path=output_path,
        original_size=original_size,
        output_size=output_path.stat().st_size,
        original_dimensions=original_dimensions,
        output_dimensions=img.size,
    )


def apply_resize(
    img: Image.Image,
    resize_mode: str,
    width: int | None,
    height: int | None,
    percentage: float | None,
) -> Image.Image:
    if resize_mode == RESIZE_NONE:
        return img

    if resize_mode == RESIZE_BY_WIDTH:
        if not width:
            raise ValueError("Width is required for width-based resizing.")

        scale = width / img.width
        new_height = max(1, round(img.height * scale))
        return img.resize((width, new_height), Image.Resampling.LANCZOS)

    if resize_mode == RESIZE_BY_HEIGHT:
        if not height:
            raise ValueError("Height is required for height-based resizing.")

        scale = height / img.height
        new_width = max(1, round(img.width * scale))
        return img.resize((new_width, height), Image.Resampling.LANCZOS)

    if resize_mode == RESIZE_EXACT:
        if not width or not height:
            raise ValueError("Width and height are required for exact resizing.")

        return img.resize((width, height), Image.Resampling.LANCZOS)

    if resize_mode == RESIZE_PERCENT:
        if not percentage:
            raise ValueError("Percentage is required for percentage scaling.")

        return resize_image(img, percentage / 100)

    raise ValueError(f"Unknown resize mode: {resize_mode}")


def _encode_to_limit(
    img: Image.Image,
    out_format: str,
    quality: int,
    max_bytes: int | None,
) -> bytes:
    if max_bytes is None:
        return save_image_to_bytes(img, out_format, quality=quality)

    data = _try_encode_at_or_under(img, out_format, quality, max_bytes)

    if data is not None:
        return data

    scale = 0.95

    while True:
        working = resize_image(img, scale)

        if working.width < 40 or working.height < 40:
            break

        data = _try_encode_at_or_under(working, out_format, quality, max_bytes)

        if data is not None:
            return data

        scale *= 0.90

    raise ValueError("Could not reach the requested max file size with practical settings.")


def _try_encode_at_or_under(
    img: Image.Image,
    out_format: str,
    quality: int,
    max_bytes: int,
) -> bytes | None:
    fmt = normalize_output_format(out_format)

    if fmt in LOSSY_FORMATS:
        for q in range(quality, 19, -5):
            data = save_image_to_bytes(img, fmt, q)

            if len(data) <= max_bytes:
                return data

        return None

    data = save_image_to_bytes(img, fmt, quality)

    if len(data) <= max_bytes:
        return data

    return None
