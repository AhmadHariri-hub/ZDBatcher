import shutil
from pathlib import Path

from app.core.file_utils import unique_output_path, is_inside_folder


BATCH_BY_COUNT = "By file count"
BATCH_BY_SIZE = "By folder size"
BATCH_METHODS = [BATCH_BY_COUNT, BATCH_BY_SIZE]


def parse_batch_size(value: str) -> int:
    batch_size = int(value.strip())

    if batch_size < 1:
        raise ValueError

    return batch_size


def parse_folder_size_mb(value: str) -> int:
    mb = float(value.strip())

    if mb <= 0:
        raise ValueError

    return int(mb * 1_000_000)


def get_batch_folder_by_index(output_dir: Path, batch_index: int) -> Path:
    batch_dir = batch_folder_path(output_dir, batch_index)
    batch_dir.mkdir(parents=True, exist_ok=True)
    return batch_dir


def batch_folder_path(output_dir: Path, batch_index: int) -> Path:
    return output_dir / f"{output_dir.name}_{batch_index:03d}"


def get_batch_folder(output_dir: Path, item_number: int, batch_size: int) -> Path:
    batch_index = ((item_number - 1) // batch_size) + 1
    return get_batch_folder_by_index(output_dir, batch_index)


def should_start_new_size_batch(
    current_batch_size: int,
    next_file_size: int,
    max_batch_bytes: int,
    current_batch_file_count: int,
) -> bool:
    if current_batch_file_count == 0:
        return False

    return current_batch_size + next_file_size > max_batch_bytes


def remove_files_inside_output_folder(files: list[Path], output_dir: Path) -> list[Path]:
    if not output_dir.exists():
        return files

    return [
        file for file in files
        if not is_inside_folder(file, output_dir)
    ]


def copy_file_to_batch_folder(file: Path, batch_dir: Path) -> Path:
    extension = file.suffix.lower().lstrip(".")
    out_path = unique_output_path(batch_dir, file.stem, extension)
    shutil.copy2(file, out_path)
    return out_path


def move_file_to_batch_folder(file: Path, batch_dir: Path) -> Path:
    extension = file.suffix.lower().lstrip(".")
    out_path = unique_output_path(batch_dir, file.stem, extension)
    shutil.move(str(file), out_path)
    return out_path


def format_bytes(size_bytes: int) -> str:
    if size_bytes >= 1_000_000_000:
        return f"{size_bytes / 1_000_000_000:.2f} GB"

    if size_bytes >= 1_000_000:
        return f"{size_bytes / 1_000_000:.1f} MB"

    if size_bytes >= 1_000:
        return f"{size_bytes / 1_000:.1f} KB"

    return f"{size_bytes} B"
