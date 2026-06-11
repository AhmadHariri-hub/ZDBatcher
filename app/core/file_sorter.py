import shutil
from dataclasses import dataclass
from pathlib import Path

from app.config import SUPPORTED_INPUTS
from app.core.audio_converter import AUDIO_INPUT_EXTENSIONS
from app.core.file_utils import is_inside_folder, natural_sort_key, unique_output_path
from app.core.video_converter import SUPPORTED_VIDEO_INPUTS


MEDIA_IMAGES = "Images"
MEDIA_VIDEOS = "Videos"
MEDIA_AUDIO = "Audio"
MEDIA_TYPES = [MEDIA_IMAGES, MEDIA_VIDEOS, MEDIA_AUDIO]

MODE_COPY = "Copy files"
MODE_MOVE = "Move files"
OPERATION_MODES = [MODE_COPY, MODE_MOVE]

STRUCTURE_CATEGORY_EXTENSION = "Category / Extension"
STRUCTURE_EXTENSION_ONLY = "Extension only"
STRUCTURE_CATEGORY_ONLY = "Category only"
FOLDER_STRUCTURES = [
    STRUCTURE_CATEGORY_EXTENSION,
    STRUCTURE_EXTENSION_ONLY,
    STRUCTURE_CATEGORY_ONLY,
]


@dataclass(frozen=True)
class SortPlanItem:
    source: Path
    media_type: str
    extension: str
    target_folder: Path


@dataclass(frozen=True)
class SortPreview:
    items: list[SortPlanItem]
    unsupported: list[Path]
    output_skipped: list[Path]

    @property
    def counts(self) -> dict[str, int]:
        return {
            media_type: sum(1 for item in self.items if item.media_type == media_type)
            for media_type in MEDIA_TYPES
        }


def classify_file(path: Path) -> tuple[str, str] | None:
    suffix = path.suffix.lower()

    if not suffix:
        return None

    extension = suffix.lstrip(".")

    # GIFs are sorted with image files in this organizer, matching the folder example.
    if suffix in SUPPORTED_INPUTS:
        return MEDIA_IMAGES, extension

    if suffix in SUPPORTED_VIDEO_INPUTS:
        return MEDIA_VIDEOS, extension

    if suffix in AUDIO_INPUT_EXTENSIONS:
        return MEDIA_AUDIO, extension

    return None


def collect_sort_preview(
    input_dir: Path,
    output_dir: Path,
    include_subfolders: bool,
    enabled_media_types: set[str],
    folder_structure: str,
) -> SortPreview:
    paths = input_dir.rglob("*") if include_subfolders else input_dir.iterdir()
    items = []
    unsupported = []
    output_skipped = []

    for path in sorted((p for p in paths if p.is_file()), key=natural_sort_key):
        if output_dir.exists() and is_inside_folder(path, output_dir):
            output_skipped.append(path)
            continue

        classified = classify_file(path)

        if classified is None:
            unsupported.append(path)
            continue

        media_type, extension = classified

        if media_type not in enabled_media_types:
            unsupported.append(path)
            continue

        items.append(
            SortPlanItem(
                source=path,
                media_type=media_type,
                extension=extension,
                target_folder=get_target_folder(output_dir, media_type, extension, folder_structure),
            )
        )

    return SortPreview(
        items=items,
        unsupported=unsupported,
        output_skipped=output_skipped,
    )


def get_target_folder(
    output_dir: Path,
    media_type: str,
    extension: str,
    folder_structure: str,
) -> Path:
    extension = extension.lower().lstrip(".")

    if folder_structure == STRUCTURE_CATEGORY_EXTENSION:
        return output_dir / media_type / extension

    if folder_structure == STRUCTURE_EXTENSION_ONLY:
        return output_dir / extension

    if folder_structure == STRUCTURE_CATEGORY_ONLY:
        return output_dir / media_type

    raise ValueError(f"Unknown folder structure: {folder_structure}")


def sort_file(item: SortPlanItem, operation_mode: str) -> Path:
    out_path = unique_output_path(item.target_folder, item.source.stem, item.extension)

    if operation_mode == MODE_COPY:
        shutil.copy2(item.source, out_path)
        return out_path

    if operation_mode == MODE_MOVE:
        shutil.move(str(item.source), out_path)
        return out_path

    raise ValueError(f"Unknown operation mode: {operation_mode}")
