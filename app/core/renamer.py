import shutil
import re
from dataclasses import dataclass
from pathlib import Path

from app.config import SUPPORTED_INPUTS
from app.core.audio_converter import AUDIO_INPUT_EXTENSIONS
from app.core.file_utils import is_inside_folder
from app.core.video_converter import SUPPORTED_VIDEO_INPUTS


FILE_FILTER_ALL = "All files"
FILE_FILTER_IMAGES = "Images"
FILE_FILTER_VIDEOS = "Videos / GIFs"
FILE_FILTER_AUDIO = "Audio"
FILE_FILTER_SUPPORTED_MEDIA = "All supported media"

SORT_NAME_ASC = "Name A-Z"
SORT_CREATED_OLD_FIRST = "Date created oldest first"
SORT_CREATED_NEW_FIRST = "Date created newest first"
SORT_MODIFIED_OLD_FIRST = "Date modified oldest first"
SORT_MODIFIED_NEW_FIRST = "Date modified newest first"

FILE_FILTERS = [
    FILE_FILTER_ALL,
    FILE_FILTER_IMAGES,
    FILE_FILTER_VIDEOS,
    FILE_FILTER_AUDIO,
    FILE_FILTER_SUPPORTED_MEDIA,
]
SORT_MODES = [
    SORT_NAME_ASC,
    SORT_CREATED_OLD_FIRST,
    SORT_CREATED_NEW_FIRST,
    SORT_MODIFIED_OLD_FIRST,
    SORT_MODIFIED_NEW_FIRST,
]

RENAME_GLOBAL = "Global"
RENAME_MEDIA_TYPE = "Per media type"
RENAME_EXTENSION = "Per extension"
RENAME_MODES = [RENAME_GLOBAL, RENAME_MEDIA_TYPE, RENAME_EXTENSION]

NUMBERING_INTERNAL = "Internal counter"
NUMBERING_FOLDER_BASED = "Folder-based next number"
NUMBERING_SOURCES = [NUMBERING_INTERNAL, NUMBERING_FOLDER_BASED]

RENAME_MEDIA_IMAGES = "Images"
RENAME_MEDIA_VIDEOS = "Videos"
RENAME_MEDIA_AUDIO = "Audio"
RENAME_MEDIA_OTHER = "Other"


@dataclass(frozen=True)
class RenamePlanItem:
    source: Path
    relative_path: Path
    group_key: str
    number: int
    relative_folder: Path = Path()
    padding: int = 0
    preserve_extension: bool = True
    prefix: str = ""
    match_extension: bool = False


def parse_starting_number(value: str) -> int:
    number = int(value.strip())

    if number < 0:
        raise ValueError

    return number


def parse_padding(value: str) -> int:
    padding = int(value.strip())

    if padding < 0:
        raise ValueError

    return padding


def get_renamable_files(
    input_dir: Path,
    include_subfolders: bool,
    file_filter: str,
    output_dir: Path | None = None,
) -> list[Path]:
    paths = input_dir.rglob("*") if include_subfolders else input_dir.iterdir()

    files = [
        path for path in paths
        if path.is_file() and _matches_filter(path, file_filter)
    ]

    if output_dir is not None and output_dir.exists():
        files = [
            path for path in files
            if not is_inside_folder(path, output_dir)
        ]

    return files


def sort_files(files: list[Path], sort_mode: str) -> list[Path]:
    if sort_mode == SORT_CREATED_OLD_FIRST:
        return sorted(files, key=lambda path: (path.stat().st_ctime, path.name.lower()))

    if sort_mode == SORT_CREATED_NEW_FIRST:
        return sorted(files, key=lambda path: (-path.stat().st_ctime, path.name.lower()))

    if sort_mode == SORT_MODIFIED_OLD_FIRST:
        return sorted(files, key=lambda path: (path.stat().st_mtime, path.name.lower()))

    if sort_mode == SORT_MODIFIED_NEW_FIRST:
        return sorted(files, key=lambda path: (-path.stat().st_mtime, path.name.lower()))

    return sorted(files, key=lambda path: path.name.lower())


def numbered_filename(
    source_file: Path,
    number: int,
    padding: int,
    preserve_extension: bool,
    prefix: str = "",
) -> str:
    number_text = str(number).zfill(padding) if padding > 0 else str(number)
    stem = f"{prefix}{number_text}"
    extension = source_file.suffix if preserve_extension else ""
    return f"{stem}{extension}"


def build_rename_plan(
    files: list[Path],
    starting_number: int,
    padding: int,
    preserve_extension: bool,
    rename_mode: str = RENAME_GLOBAL,
    prefix: str = "",
    numbering_source: str = NUMBERING_INTERNAL,
    output_dir: Path | None = None,
    target_dir_for_item=None,
    limit: int | None = None,
) -> list[RenamePlanItem]:
    counters: dict[str, int] = {}
    reserved_paths: set[Path] = set()
    planned_files = files[:limit] if limit is not None else files
    plan = []

    for index, file in enumerate(planned_files, start=1):
        group_key, relative_folder = rename_group(file, rename_mode)
        base_dir = _target_base_dir(output_dir, target_dir_for_item, index, file)
        target_dir = base_dir / relative_folder
        match_extension = rename_mode == RENAME_EXTENSION
        sequence_key = _sequence_key(numbering_source, group_key, target_dir, prefix, padding, preserve_extension, match_extension, file.suffix)
        number = determine_next_number(
            target_dir=target_dir,
            source_file=file,
            starting_number=starting_number,
            padding=padding,
            preserve_extension=preserve_extension,
            prefix=prefix,
            numbering_source=numbering_source,
            counters=counters,
            sequence_key=sequence_key,
            reserved_paths=reserved_paths,
            match_extension=match_extension,
        )
        filename = numbered_filename(file, number, padding, preserve_extension, prefix)
        relative_path = relative_folder / filename if relative_folder != Path() else Path(filename)
        reserved_paths.add(target_dir / filename)
        plan.append(
            RenamePlanItem(
                source=file,
                relative_path=relative_path,
                group_key=group_key,
                number=number,
                relative_folder=relative_folder,
                padding=padding,
                preserve_extension=preserve_extension,
                prefix=prefix,
                match_extension=match_extension,
            )
        )

    return plan


def preview_names(
    files: list[Path],
    starting_number: int,
    padding: int,
    preserve_extension: bool,
    rename_mode: str = RENAME_GLOBAL,
    prefix: str = "",
    numbering_source: str = NUMBERING_INTERNAL,
    output_dir: Path | None = None,
    target_dir_for_item=None,
    limit: int = 200,
) -> list[tuple[Path, str]]:
    return [
        (item.source, item.relative_path.as_posix())
        for item in build_rename_plan(
            files=files,
            starting_number=starting_number,
            padding=padding,
            preserve_extension=preserve_extension,
            rename_mode=rename_mode,
            prefix=prefix,
            numbering_source=numbering_source,
            output_dir=output_dir,
            target_dir_for_item=target_dir_for_item,
            limit=limit,
        )
    ]


def copy_renamed_file(
    source_file: Path,
    output_dir: Path,
    number: int,
    padding: int,
    preserve_extension: bool,
    prefix: str = "",
) -> Path:
    out_path = build_numbered_output_path(
        target_dir=output_dir,
        source_file=source_file,
        starting_number=number,
        padding=padding,
        preserve_extension=preserve_extension,
        prefix=prefix,
    )
    shutil.copy2(source_file, out_path)
    return out_path


def copy_rename_plan_item(item: RenamePlanItem, output_dir: Path) -> Path:
    target_dir = output_dir / item.relative_folder
    out_path = build_numbered_output_path(
        target_dir=target_dir,
        source_file=item.source,
        starting_number=item.number,
        padding=item.padding,
        preserve_extension=item.preserve_extension,
        prefix=item.prefix,
        match_extension=item.match_extension,
    )
    shutil.copy2(item.source, out_path)
    return out_path


def copy_renamed_relative_path(source_file: Path, output_dir: Path, relative_path: Path) -> Path:
    target_parent = output_dir / relative_path.parent
    out_path = unique_renamed_path(target_parent, relative_path.stem, relative_path.suffix)
    shutil.copy2(source_file, out_path)
    return out_path


def determine_next_number(
    *,
    target_dir: Path,
    source_file: Path,
    starting_number: int,
    padding: int,
    preserve_extension: bool,
    prefix: str = "",
    numbering_source: str = NUMBERING_INTERNAL,
    counters: dict[str, int] | None = None,
    sequence_key: str | None = None,
    reserved_paths: set[Path] | None = None,
    match_extension: bool = False,
) -> int:
    if numbering_source == NUMBERING_FOLDER_BASED:
        number = max(starting_number, scan_highest_existing_number(target_dir, source_file, padding, preserve_extension, prefix, match_extension) + 1)
    else:
        key = sequence_key or RENAME_GLOBAL
        if counters is None:
            counters = {}
        number = counters.get(key, starting_number)

    while _numbered_candidate_path(target_dir, source_file, number, padding, preserve_extension, prefix).exists():
        number += 1

    if reserved_paths is not None:
        while _numbered_candidate_path(target_dir, source_file, number, padding, preserve_extension, prefix) in reserved_paths:
            number += 1

    if numbering_source != NUMBERING_FOLDER_BASED and counters is not None:
        key = sequence_key or RENAME_GLOBAL
        counters[key] = number + 1

    return number


def scan_highest_existing_number(
    target_dir: Path,
    source_file: Path,
    padding: int,
    preserve_extension: bool,
    prefix: str = "",
    match_extension: bool = False,
) -> int:
    if not target_dir.exists() or not target_dir.is_dir():
        return 0

    highest = 0

    for path in target_dir.iterdir():
        if not path.is_file():
            continue

        number = matching_number(
            path=path,
            source_file=source_file,
            padding=padding,
            preserve_extension=preserve_extension,
            prefix=prefix,
            match_extension=match_extension,
        )

        if number is not None:
            highest = max(highest, number)

    return highest


def matching_number(
    *,
    path: Path,
    source_file: Path,
    padding: int,
    preserve_extension: bool,
    prefix: str = "",
    match_extension: bool = False,
) -> int | None:
    if preserve_extension:
        if match_extension and path.suffix.lower() != source_file.suffix.lower():
            return None
        name = path.stem
    else:
        if path.suffix:
            return None
        name = path.name

    digits = rf"\d{{{padding},}}" if padding > 0 else r"(?:0|[1-9]\d*)"
    match = re.fullmatch(rf"{re.escape(prefix)}({digits})", name)

    if match is None:
        return None

    return int(match.group(1))


def build_numbered_output_path(
    *,
    target_dir: Path,
    source_file: Path,
    starting_number: int,
    padding: int,
    preserve_extension: bool,
    prefix: str = "",
    match_extension: bool = False,
) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    number = starting_number

    while True:
        path = _numbered_candidate_path(target_dir, source_file, number, padding, preserve_extension, prefix)
        if not path.exists():
            return path
        number += 1


def rename_group(source_file: Path, rename_mode: str) -> tuple[str, Path]:
    if rename_mode == RENAME_MEDIA_TYPE:
        media_type = classify_media_type(source_file)
        return media_type, Path(media_type)

    if rename_mode == RENAME_EXTENSION:
        extension = source_file.suffix.lower().lstrip(".") or "no_extension"
        return extension, Path(extension)

    return RENAME_GLOBAL, Path()


def classify_media_type(path: Path) -> str:
    suffix = path.suffix.lower()

    if suffix in SUPPORTED_VIDEO_INPUTS:
        return RENAME_MEDIA_VIDEOS

    if suffix in AUDIO_INPUT_EXTENSIONS:
        return RENAME_MEDIA_AUDIO

    if suffix in SUPPORTED_INPUTS:
        return RENAME_MEDIA_IMAGES

    return RENAME_MEDIA_OTHER


def is_image_file(path: Path) -> bool:
    suffix = path.suffix.lower()
    return suffix in SUPPORTED_INPUTS and suffix not in SUPPORTED_VIDEO_INPUTS


def is_video_file(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_VIDEO_INPUTS


def is_audio_file(path: Path) -> bool:
    return path.suffix.lower() in AUDIO_INPUT_EXTENSIONS


def is_supported_media_file(path: Path) -> bool:
    return is_image_file(path) or is_video_file(path) or is_audio_file(path)


def unique_renamed_path(output_dir: Path, stem: str, extension: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    extension = extension.lstrip(".")
    suffix = f".{extension}" if extension else ""
    path = output_dir / f"{stem}{suffix}"
    counter = 1

    while path.exists():
        path = output_dir / f"{stem}_{counter}{suffix}"
        counter += 1

    return path


def _target_base_dir(output_dir: Path | None, target_dir_for_item, index: int, file: Path) -> Path:
    if target_dir_for_item is not None:
        return Path(target_dir_for_item(index, file))

    if output_dir is not None:
        return Path(output_dir)

    return Path()


def _numbered_candidate_path(
    target_dir: Path,
    source_file: Path,
    number: int,
    padding: int,
    preserve_extension: bool,
    prefix: str = "",
) -> Path:
    return target_dir / numbered_filename(source_file, number, padding, preserve_extension, prefix)


def _sequence_key(
    numbering_source: str,
    group_key: str,
    target_dir: Path,
    prefix: str,
    padding: int,
    preserve_extension: bool,
    match_extension: bool,
    extension: str,
) -> str:
    if numbering_source == NUMBERING_FOLDER_BASED:
        return "|".join([
            str(target_dir.resolve() if target_dir.exists() else target_dir.absolute()),
            group_key,
            prefix,
            str(padding),
            str(preserve_extension),
            str(match_extension),
            extension.lower() if match_extension else "",
        ])

    return group_key


def _matches_filter(path: Path, file_filter: str) -> bool:
    if file_filter == FILE_FILTER_ALL:
        return True

    if file_filter == FILE_FILTER_IMAGES:
        return is_image_file(path)

    if file_filter == FILE_FILTER_VIDEOS:
        return is_video_file(path)

    if file_filter == FILE_FILTER_AUDIO:
        return is_audio_file(path)

    if file_filter == FILE_FILTER_SUPPORTED_MEDIA:
        return is_supported_media_file(path)

    return True
