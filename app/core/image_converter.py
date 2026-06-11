import io
from pathlib import Path

from PIL import Image, ImageOps

from app.config import BASE_OUTPUT_FORMATS, LOSSY_FORMATS
from app.core.svg_utils import svg_to_png_bytes


OUTPUT_FORMAT_ALIASES = {
    "jpeg": "jpg",
    "tif": "tiff",
}

SUPPORTED_OUTPUT_FORMATS = {"jpg", "png", "webp", "avif", "tiff", "bmp"}


try:
    import pillow_avif as _pillow_avif
except Exception:
    _pillow_avif = None

try:
    import pillow_heif as _pillow_heif
    _pillow_heif.register_heif_opener()
except Exception:
    _pillow_heif = None


def avif_available() -> bool:
    return _pillow_avif is not None


def heif_available() -> bool:
    return _pillow_heif is not None


def get_output_formats() -> list[str]:
    formats = list(BASE_OUTPUT_FORMATS)

    if avif_available():
        formats.insert(3, "avif")

    return formats


def normalize_output_format(out_format: str) -> str:
    fmt = out_format.lower().lstrip(".")
    fmt = OUTPUT_FORMAT_ALIASES.get(fmt, fmt)

    if fmt not in SUPPORTED_OUTPUT_FORMATS:
        raise ValueError(f"Unsupported output format: {out_format}")

    return fmt


def output_extension_for_format(out_format: str) -> str:
    return normalize_output_format(out_format)


def original_output_format(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    fmt = OUTPUT_FORMAT_ALIASES.get(suffix, suffix)

    if fmt not in set(get_output_formats()):
        raise ValueError(
            f"Cannot resize {path.suffix.upper()} while preserving its original format. "
            "Use Image Conversion first."
        )

    return fmt


def safe_max_bytes(max_mb: str) -> int:
    value = float(max_mb)
    return max(1, int(value * 1_000_000) - 1024)


def open_image(path: Path) -> Image.Image:
    suffix = path.suffix.lower()

    if suffix == ".svg":
        png_data = svg_to_png_bytes(path)
        img = Image.open(io.BytesIO(png_data))
    else:
        img = Image.open(path)

    img.load()
    img = ImageOps.exif_transpose(img)
    return img


def prepare_image(img: Image.Image, out_format: str) -> Image.Image:
    fmt = normalize_output_format(out_format)

    if fmt in {"jpg", "bmp"}:
        if img.mode in {"RGBA", "LA", "P"} or "transparency" in img.info:
            img = img.convert("RGBA")
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            return bg

        return img.convert("RGB")

    if fmt in {"png", "webp", "avif"}:
        if img.mode not in {"RGB", "RGBA"}:
            return img.convert("RGBA")

        return img

    if fmt == "tiff":
        if img.mode not in {"RGB", "RGBA", "L"}:
            return img.convert("RGB")

        return img

    raise ValueError(f"Unsupported output format: {fmt}")


def save_image_to_bytes(img: Image.Image, out_format: str, quality: int = 90) -> bytes:
    buf = io.BytesIO()
    fmt = normalize_output_format(out_format)

    kwargs = {}
    pil_fmt = fmt.upper()

    if fmt == "jpg":
        fmt = "jpeg"
        pil_fmt = "JPEG"

    if fmt in {"jpeg", "webp", "avif"}:
        kwargs["quality"] = quality
        kwargs["optimize"] = True

    if fmt == "jpeg":
        kwargs["progressive"] = True

    if fmt == "png":
        kwargs["optimize"] = True
        kwargs["compress_level"] = 9

    if fmt == "tiff":
        kwargs["compression"] = "tiff_lzw"

    img.save(buf, format=pil_fmt, **kwargs)
    return buf.getvalue()


def resize_image(img: Image.Image, scale: float) -> Image.Image:
    w = max(1, int(img.width * scale))
    h = max(1, int(img.height * scale))
    return img.resize((w, h), Image.Resampling.LANCZOS)


def convert_image(
    input_path: Path,
    output_path: Path,
    out_format: str,
) -> bool:
    img = open_image(input_path)
    img = prepare_image(img, out_format)
    data = save_image_to_bytes(img, out_format, quality=95)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)
    return True


def compress_image(
    input_path: Path,
    output_path: Path,
    out_format: str,
    max_bytes: int,
) -> bool:
    img = open_image(input_path)
    img = prepare_image(img, out_format)
    fmt = normalize_output_format(out_format)

    def try_save(working_img, quality=90):
        if fmt in LOSSY_FORMATS:
            for q in range(quality, 19, -5):
                data = save_image_to_bytes(working_img, fmt, q)

                if len(data) <= max_bytes:
                    return data
        else:
            data = save_image_to_bytes(working_img, fmt)

            if len(data) <= max_bytes:
                return data

        return None

    data = try_save(img)

    if data:
        output_path.write_bytes(data)
        return True

    scale = 0.95

    while True:
        working = resize_image(img, scale)

        if working.width < 40 or working.height < 40:
            break

        data = try_save(working)

        if data:
            output_path.write_bytes(data)
            return True

        scale *= 0.90

    if fmt in LOSSY_FORMATS:
        tiny = resize_image(img, 0.20)
        data = save_image_to_bytes(tiny, fmt, 20)

        if len(data) <= max_bytes:
            output_path.write_bytes(data)
            return True

    if output_path.exists():
        output_path.unlink()

    return False
