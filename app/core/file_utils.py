import re
from pathlib import Path

from app.config import SUPPORTED_INPUTS


def natural_sort_key(path: Path):
    parts = re.split(r"(\d+)", path.name.lower())
    return [int(part) if part.isdigit() else part for part in parts]


def get_supported_files(input_dir: Path, include_subfolders: bool) -> list[Path]:
    paths = input_dir.rglob("*") if include_subfolders else input_dir.iterdir()

    return sorted(
        [
            p for p in paths
            if p.is_file() and p.suffix.lower() in SUPPORTED_INPUTS
        ],
        key=natural_sort_key,
    )


def unique_output_path(output_dir: Path, stem: str, extension: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    extension = extension.lower().lstrip(".")
    path = output_dir / f"{stem}.{extension}"
    counter = 1

    while path.exists():
        path = output_dir / f"{stem}_{counter}.{extension}"
        counter += 1

    return path


def is_inside_folder(path: Path, folder: Path) -> bool:
    try:
        path.resolve().relative_to(folder.resolve())
        return True
    except ValueError:
        return False