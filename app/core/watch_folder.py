import queue
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from app.config import SUPPORTED_INPUTS
from app.core.audio_converter import (
    AUDIO_INPUT_EXTENSIONS,
    FILTER_AUDIO_AND_VIDEO,
    FILTER_AUDIO_ONLY,
    QUALITY_BALANCED as AUDIO_QUALITY_BALANCED,
    VIDEO_AUDIO_INPUT_EXTENSIONS,
    convert_audio,
    input_filter_includes_video,
)
from app.core.batcher import BATCH_BY_COUNT, BATCH_BY_SIZE, get_batch_folder_by_index, should_start_new_size_batch
from app.core.file_sorter import (
    FOLDER_STRUCTURES,
    MEDIA_TYPES as SORT_MEDIA_TYPES,
    classify_file,
    get_target_folder,
)
from app.core.file_utils import is_inside_folder, unique_output_path
from app.core.image_converter import convert_image, original_output_format
from app.core.image_resizer import (
    QUALITY_BALANCED as IMAGE_QUALITY_BALANCED,
    RESIZE_BY_HEIGHT as IMAGE_RESIZE_BY_HEIGHT,
    RESIZE_BY_WIDTH as IMAGE_RESIZE_BY_WIDTH,
    RESIZE_EXACT as IMAGE_RESIZE_EXACT,
    RESIZE_NONE as IMAGE_RESIZE_NONE,
    RESIZE_PERCENT as IMAGE_RESIZE_PERCENT,
    resize_and_compress_image,
)
from app.core.media_engine import find_ffmpeg
from app.core.video_converter import (
    GIF_FPS_ORIGINAL,
    GIF_WIDTH_KEEP,
    OUTPUT_VIDEO_FORMATS,
    QUALITY_BALANCED as VIDEO_QUALITY_BALANCED,
    RESIZE_KEEP as VIDEO_CONVERT_RESIZE_KEEP,
    SUPPORTED_VIDEO_INPUTS,
    convert_video,
)
from app.core.video_resizer import (
    PRESET_1080,
    RESIZABLE_VIDEO_OUTPUT_FORMATS,
    RESIZE_CUSTOM as VIDEO_RESIZE_CUSTOM,
    RESIZE_NONE as VIDEO_RESIZE_NONE,
    RESIZE_PERCENT as VIDEO_RESIZE_PERCENT,
    RESIZE_PRESET as VIDEO_RESIZE_PRESET,
    resize_video,
)
from app.core.renamer import (
    NUMBERING_INTERNAL,
    determine_next_number,
    RENAME_EXTENSION,
    RENAME_GLOBAL,
    numbered_filename,
    rename_group,
)


try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    WATCHDOG_AVAILABLE = True
except Exception:
    FileSystemEventHandler = object
    Observer = None
    WATCHDOG_AVAILABLE = False


MEDIA_IMAGE = "image"
MEDIA_VIDEO = "video"
MEDIA_AUDIO = "audio"

MEDIA_LABELS = {
    MEDIA_IMAGE: "Image",
    MEDIA_VIDEO: "Video",
    MEDIA_AUDIO: "Audio",
}

SORT_MEDIA_FOLDERS = {
    MEDIA_IMAGE: "Images",
    MEDIA_VIDEO: "Videos",
    MEDIA_AUDIO: "Audio",
}

STATUS_STOPPED = "Stopped"
STATUS_WATCHING = "Watching"
STATUS_PAUSED = "Paused"
STATUS_PROCESSING = "Processing"

TEMP_SUFFIXES = {
    ".tmp",
    ".part",
    ".crdownload",
    ".download",
    ".~tmp",
}

EVENT_STATUS = "status"
EVENT_LOG = "log"
EVENT_QUEUE = "queue"
EVENT_CURRENT = "current"
EVENT_PROGRESS = "progress"


@dataclass(frozen=True)
class ImageRules:
    convert: bool = False
    convert_output_format: str = "jpg"
    resize: bool = False
    resize_mode: str = IMAGE_RESIZE_BY_WIDTH
    width: int | None = None
    height: int | None = None
    percentage: float | None = None
    max_bytes: int | None = None
    quality_preset: str = IMAGE_QUALITY_BALANCED

    @property
    def enabled(self) -> bool:
        return self.convert or self.resize


@dataclass(frozen=True)
class VideoRules:
    convert: bool = False
    convert_output_format: str = "mp4"
    convert_quality_preset: str = VIDEO_QUALITY_BALANCED
    convert_resize_option: str = VIDEO_CONVERT_RESIZE_KEEP
    gif_fps: str = GIF_FPS_ORIGINAL
    gif_width_option: str = GIF_WIDTH_KEEP
    gif_custom_width: int | None = None
    resize: bool = False
    resize_mode: str = VIDEO_RESIZE_PRESET
    preset_resolution: str = PRESET_1080
    width: int | None = None
    height: int | None = None
    percentage: float | None = None
    target_bytes: int | None = None
    resize_quality_preset: str = VIDEO_QUALITY_BALANCED

    @property
    def enabled(self) -> bool:
        return self.convert or self.resize


@dataclass(frozen=True)
class AudioRules:
    enabled: bool = False
    input_filter: str = FILTER_AUDIO_ONLY
    output_format: str = "mp3"
    quality_preset: str = AUDIO_QUALITY_BALANCED

    @property
    def handles_audio(self) -> bool:
        return self.enabled and self.input_filter in {FILTER_AUDIO_ONLY, FILTER_AUDIO_AND_VIDEO}

    @property
    def handles_video(self) -> bool:
        return self.enabled and input_filter_includes_video(self.input_filter)


@dataclass(frozen=True)
class SortingRules:
    enabled: bool = False
    folder_structure: str = FOLDER_STRUCTURES[0]
    media_types: frozenset[str] = frozenset(SORT_MEDIA_TYPES)


@dataclass(frozen=True)
class RenamingRules:
    enabled: bool = False
    numbering_mode: str = RENAME_GLOBAL
    numbering_source: str = NUMBERING_INTERNAL
    starting_number: int = 1
    padding: int = 0
    prefix: str = ""
    preserve_extension: bool = True


@dataclass(frozen=True)
class BatchRules:
    enabled: bool = False
    method: str = BATCH_BY_COUNT
    files_per_folder: int = 40
    max_folder_bytes: int = 100_000_000


@dataclass(frozen=True)
class WatchSettings:
    input_folder: Path
    output_folder: Path
    include_subfolders: bool = False
    process_existing: bool = False
    image: ImageRules = field(default_factory=ImageRules)
    video: VideoRules = field(default_factory=VideoRules)
    audio: AudioRules = field(default_factory=AudioRules)
    sorting: SortingRules = field(default_factory=SortingRules)
    renaming: RenamingRules = field(default_factory=RenamingRules)
    batch: BatchRules = field(default_factory=BatchRules)
    stable_interval_seconds: float = 1.0
    stable_timeout_seconds: float = 300.0


@dataclass(frozen=True)
class WatchResult:
    source: Path
    output: Path | None
    media_type: str | None
    skipped: bool = False
    message: str = ""


class WatchSessionState:
    def __init__(self, settings: WatchSettings):
        self._settings = settings
        self._rename_next: dict[str, int] = {}
        self._batch_index = 1
        self._batch_size = 0
        self._batch_count = 0
        self._processed_count = 0

    def next_relative_path(self, source: Path, extension: str, target_dir: Path) -> Path:
        rules = self._settings.renaming
        extension = extension.lower().lstrip(".")
        current_name = f"{source.stem}.{extension}" if extension else source.stem
        current_path = Path(current_name)

        if not rules.enabled:
            return current_path

        key, folder = rename_group(current_path, rules.numbering_mode)
        match_extension = rules.numbering_mode == RENAME_EXTENSION
        number = determine_next_number(
            target_dir=target_dir / folder,
            source_file=current_path,
            starting_number=rules.starting_number,
            padding=rules.padding,
            preserve_extension=rules.preserve_extension,
            prefix=rules.prefix,
            numbering_source=rules.numbering_source,
            counters=self._rename_next,
            sequence_key=key,
            match_extension=match_extension,
        )
        filename = numbered_filename(current_path, number, rules.padding, rules.preserve_extension, rules.prefix)
        return folder / filename if folder != Path() else Path(filename)

    def reserve_base_dir(self, output_dir: Path, next_file_size: int) -> Path:
        rules = self._settings.batch

        if not rules.enabled:
            return output_dir

        if rules.method == BATCH_BY_COUNT:
            index = (self._processed_count // max(1, rules.files_per_folder)) + 1
            return get_batch_folder_by_index(output_dir, index)

        if should_start_new_size_batch(
            current_batch_size=self._batch_size,
            next_file_size=next_file_size,
            max_batch_bytes=rules.max_folder_bytes,
            current_batch_file_count=self._batch_count,
        ):
            self._batch_index += 1
            self._batch_size = 0
            self._batch_count = 0

        return get_batch_folder_by_index(output_dir, self._batch_index)

    def mark_output_written(self, output_path: Path):
        size = output_path.stat().st_size if output_path.exists() else 0
        self._processed_count += 1

        if self._settings.batch.enabled and self._settings.batch.method == BATCH_BY_SIZE:
            self._batch_size += size
            self._batch_count += 1


class WatchFolderService:
    def __init__(self, event_callback: Callable[[dict], None] | None = None):
        self._event_callback = event_callback
        self._queue: queue.Queue[Path] = queue.Queue()
        self._queued_paths: set[str] = set()
        self._active_paths: set[str] = set()
        self._processed_paths: set[str] = set()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._poll_thread: threading.Thread | None = None
        self._observer = None
        self._settings: WatchSettings | None = None
        self._state: WatchSessionState | None = None
        self._accepting = False
        self._current: Path | None = None

    @property
    def running(self) -> bool:
        return self._accepting

    @property
    def using_watchdog(self) -> bool:
        return self._observer is not None

    def start(self, settings: WatchSettings):
        if self._accepting:
            raise RuntimeError("Watcher is already running.")

        settings = _normalize_settings(settings)
        _validate_settings(settings)

        self._settings = settings
        self._state = WatchSessionState(settings)
        self._queued_paths.clear()
        self._active_paths.clear()
        self._processed_paths.clear()
        self._stop_event.clear()
        self._accepting = True

        if not settings.process_existing:
            for path in _iter_candidate_files(settings):
                self._processed_paths.add(_path_key(path))

        self._worker_thread = threading.Thread(target=self._worker_loop, name="ZDBatcherWatchWorker", daemon=True)
        self._worker_thread.start()

        if WATCHDOG_AVAILABLE:
            self._start_watchdog(settings)
        else:
            self._start_polling(settings)

        if settings.process_existing:
            for path in _iter_candidate_files(settings):
                self.enqueue(path, detected=False)

        backend = "watchdog" if self.using_watchdog else "polling"
        self._emit(EVENT_STATUS, status=STATUS_WATCHING, message=f"Watching with {backend}.")
        self._emit(EVENT_LOG, text="Watcher started", tag="info")
        self._emit_engine_status()
        self._emit_queue_count()

    def stop(self):
        if not self._accepting and self._current is None:
            self._emit(EVENT_STATUS, status=STATUS_STOPPED, message="Watcher stopped.")
            return

        self._accepting = False
        self._stop_event.set()
        self._stop_observer()
        self.clear_queue(emit=False)
        self._emit(EVENT_LOG, text="Watcher stopped", tag="info")

        if self._current is None:
            self._emit(EVENT_STATUS, status=STATUS_STOPPED, message="Watcher stopped.")

        self._emit_queue_count()

    def clear_queue(self, emit: bool = True):
        removed = 0

        with self._lock:
            while True:
                try:
                    self._queue.get_nowait()
                    removed += 1
                except queue.Empty:
                    break
            self._queued_paths.clear()

        if emit:
            self._emit(EVENT_LOG, text=f"Cleared {removed} queued file(s)", tag="dim")
            self._emit_queue_count()

    def enqueue(self, path: str | Path, *, detected: bool = True):
        settings = self._settings

        if not self._accepting or settings is None:
            return

        path = Path(path)

        if _should_ignore_path(path, settings):
            return

        key = _path_key(path)

        with self._lock:
            if key in self._queued_paths or key in self._active_paths or key in self._processed_paths:
                return
            self._queued_paths.add(key)
            self._queue.put(path)

        if detected:
            self._emit(EVENT_LOG, text=f"Detected file: {path.name}", tag="info")

        self._emit(EVENT_LOG, text=f"Queued file: {path.name}", tag="dim")
        self._emit_queue_count()

    def _start_watchdog(self, settings: WatchSettings):
        if Observer is None:
            self._start_polling(settings)
            return

        handler = _WatchdogHandler(self)
        self._observer = Observer()
        self._observer.schedule(handler, str(settings.input_folder), recursive=settings.include_subfolders)
        self._observer.start()

    def _start_polling(self, settings: WatchSettings):
        self._poll_thread = threading.Thread(target=self._poll_loop, args=(settings,), name="ZDBatcherWatchPoller", daemon=True)
        self._poll_thread.start()

    def _poll_loop(self, settings: WatchSettings):
        while not self._stop_event.is_set():
            for path in _iter_candidate_files(settings):
                if self._stop_event.is_set():
                    break
                self.enqueue(path)
            self._stop_event.wait(1.0)

    def _worker_loop(self):
        while True:
            if self._stop_event.is_set() and self._queue.empty():
                break

            try:
                path = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue

            key = _path_key(path)

            with self._lock:
                self._queued_paths.discard(key)
                self._active_paths.add(key)
                self._current = path

            self._emit_queue_count()
            self._emit(EVENT_CURRENT, path=str(path), name=path.name)
            self._emit(EVENT_STATUS, status=STATUS_PROCESSING, message=f"Processing {path.name}")
            self._emit(EVENT_PROGRESS, value=0, maximum=1)

            try:
                process_watch_file(
                    path,
                    self._settings,
                    self._state,
                    self._emit,
                    self._stop_event,
                )
                self._processed_paths.add(key)
            except Exception as exc:
                self._emit(EVENT_LOG, text=f"Failed {path.name}: {exc}", tag="err")
                self._processed_paths.add(key)
            finally:
                with self._lock:
                    self._active_paths.discard(key)
                    self._current = None
                self._emit(EVENT_CURRENT, path="", name="")
                self._emit(EVENT_PROGRESS, value=1, maximum=1)

                if self._accepting:
                    self._emit(EVENT_STATUS, status=STATUS_WATCHING, message="Watching for new files.")
                else:
                    self._emit(EVENT_STATUS, status=STATUS_STOPPED, message="Watcher stopped.")

                self._emit_queue_count()

    def _stop_observer(self):
        observer = self._observer
        self._observer = None

        if observer is not None:
            observer.stop()
            observer.join(timeout=2)

    def _emit_engine_status(self):
        if find_ffmpeg():
            self._emit(EVENT_LOG, text="Media engine ready", tag="ok")
        else:
            self._emit(EVENT_LOG, text="Media engine unavailable", tag="err")

    def _emit_queue_count(self):
        self._emit(EVENT_QUEUE, count=self._queue.qsize())

    def _emit(self, kind: str, **payload):
        if self._event_callback:
            self._event_callback({"kind": kind, **payload})


class _WatchdogHandler(FileSystemEventHandler):
    def __init__(self, service: WatchFolderService):
        super().__init__()
        self._service = service

    def on_created(self, event):
        self._handle(event)

    def on_modified(self, event):
        self._handle(event)

    def on_moved(self, event):
        if not getattr(event, "is_directory", False):
            self._service.enqueue(getattr(event, "dest_path", ""))

    def _handle(self, event):
        if getattr(event, "is_directory", False):
            return
        self._service.enqueue(getattr(event, "src_path", ""))


def process_watch_file(
    source: Path,
    settings: WatchSettings,
    state: WatchSessionState,
    emit: Callable[..., None] | None = None,
    stop_event: threading.Event | None = None,
) -> WatchResult:
    if emit is None:
        emit = lambda _kind, **_payload: None

    source = Path(source)

    if _should_ignore_path(source, settings):
        return WatchResult(source=source, output=None, media_type=None, skipped=True, message="Ignored file.")

    media_type = detect_media_type(source, settings)

    if media_type is None:
        message = f"Skipped unsupported file: {source.name}"
        emit(EVENT_LOG, text=message, tag="dim")
        return WatchResult(source=source, output=None, media_type=None, skipped=True, message=message)

    if not _media_enabled(media_type, settings):
        message = f"Skipped disabled {MEDIA_LABELS[media_type].lower()} file: {source.name}"
        emit(EVENT_LOG, text=message, tag="dim")
        return WatchResult(source=source, output=None, media_type=media_type, skipped=True, message=message)

    emit(EVENT_LOG, text=f"Waiting for file to finish copying: {source.name}", tag="dim")
    wait_until_file_stable(
        source,
        interval=settings.stable_interval_seconds,
        timeout=settings.stable_timeout_seconds,
        stop_event=stop_event,
    )

    emit(EVENT_LOG, text=f"Processing file: {source.name}", tag="info")
    temp_path = None
    processed_path = source
    extension = source.suffix.lower().lstrip(".")

    try:
        processed_path, extension, temp_path = _process_media(source, media_type, settings)
        final_path = _final_output_path(source, processed_path, media_type, extension, settings, state)

        final_path.parent.mkdir(parents=True, exist_ok=True)

        if processed_path == source:
            shutil.copy2(source, final_path)
        else:
            shutil.move(str(processed_path), final_path)
            temp_path = None

        state.mark_output_written(final_path)
        emit(EVENT_LOG, text=f"Done {source.name} -> {final_path.name}", tag="ok")
        return WatchResult(source=source, output=final_path, media_type=media_type, message="Done")
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def wait_until_file_stable(
    path: Path,
    *,
    interval: float = 1.0,
    timeout: float = 300.0,
    stop_event: threading.Event | None = None,
):
    start = time.monotonic()
    last_size = None
    stable_checks = 0

    while True:
        if stop_event is not None and stop_event.is_set():
            raise RuntimeError("Stopped before file became stable.")

        try:
            size = path.stat().st_size
            with path.open("rb") as handle:
                handle.seek(0, 2)
        except (FileNotFoundError, PermissionError, OSError):
            stable_checks = 0
            size = None

        if size is not None and size == last_size:
            stable_checks += 1
            if stable_checks >= 2:
                return
        else:
            stable_checks = 0
            last_size = size

        if time.monotonic() - start > timeout:
            raise TimeoutError("File did not become stable before the timeout.")

        time.sleep(interval)


def detect_media_type(path: Path, settings: WatchSettings | None = None) -> str | None:
    suffix = path.suffix.lower()

    if suffix == ".gif":
        return MEDIA_VIDEO

    if suffix in SUPPORTED_VIDEO_INPUTS:
        if settings and not settings.video.enabled and settings.audio.handles_video:
            return MEDIA_AUDIO
        return MEDIA_VIDEO

    if suffix in AUDIO_INPUT_EXTENSIONS:
        return MEDIA_AUDIO

    if suffix in VIDEO_AUDIO_INPUT_EXTENSIONS:
        return MEDIA_AUDIO

    if suffix in SUPPORTED_INPUTS:
        return MEDIA_IMAGE

    return None


def _process_media(source: Path, media_type: str, settings: WatchSettings) -> tuple[Path, str, Path | None]:
    if media_type == MEDIA_IMAGE:
        return _process_image(source, settings.image)

    if media_type == MEDIA_VIDEO:
        return _process_video(source, settings.video)

    if media_type == MEDIA_AUDIO:
        return _process_audio(source, settings.audio)

    raise ValueError(f"Unsupported media type: {media_type}")


def _process_image(source: Path, rules: ImageRules) -> tuple[Path, str, Path | None]:
    original_extension = source.suffix.lower().lstrip(".")
    should_process = rules.convert or rules.resize
    if rules.resize:
        extension = original_output_format(source)
    elif rules.convert:
        extension = rules.convert_output_format.lower().lstrip(".")
    else:
        extension = original_extension

    if not should_process:
        return source, extension, None

    temp_path = _temp_output_path(extension)

    if rules.resize:
        resize_mode, width, height, percentage, max_bytes = _image_resize_args(rules)
        resize_and_compress_image(
            input_path=source,
            output_path=temp_path,
            out_format=extension,
            resize_mode=resize_mode,
            width=width,
            height=height,
            percentage=percentage,
            quality_preset=rules.quality_preset,
            max_bytes=max_bytes,
        )
    else:
        convert_image(source, temp_path, extension)

    return temp_path, extension, temp_path


def _process_video(source: Path, rules: VideoRules) -> tuple[Path, str, Path | None]:
    original_extension = source.suffix.lower().lstrip(".")
    should_process = rules.convert or rules.resize
    if rules.resize:
        extension = original_extension
    elif rules.convert:
        extension = rules.convert_output_format.lower().lstrip(".")
    else:
        extension = original_extension

    if not should_process:
        return source, extension, None

    ffmpeg_path = find_ffmpeg()

    if not ffmpeg_path:
        raise RuntimeError("Media engine unavailable for video processing.")

    allowed_formats = RESIZABLE_VIDEO_OUTPUT_FORMATS if rules.resize else OUTPUT_VIDEO_FORMATS

    if extension not in allowed_formats:
        raise ValueError(f"Unsupported output video format: {extension}")

    temp_path = _temp_output_path(extension)

    if rules.resize:
        resize_mode, preset, width, height, percentage, target_bytes = _video_resize_args(rules)
        resize_video(
            ffmpeg_path=ffmpeg_path,
            input_file=source,
            output_file=temp_path,
            output_format=extension,
            resize_mode=resize_mode,
            preset_resolution=preset,
            width=width,
            height=height,
            percentage=percentage,
            quality_preset=rules.resize_quality_preset,
            target_bytes=target_bytes,
        )
    else:
        convert_video(
            ffmpeg_path=ffmpeg_path,
            input_file=source,
            output_file=temp_path,
            output_format=extension,
            quality_preset=rules.convert_quality_preset,
            resize_option=rules.convert_resize_option,
            gif_fps=rules.gif_fps,
            gif_width_option=rules.gif_width_option,
            gif_custom_width=rules.gif_custom_width,
        )

    return temp_path, extension, temp_path


def _process_audio(source: Path, rules: AudioRules) -> tuple[Path, str, Path | None]:
    original_extension = source.suffix.lower().lstrip(".")
    source_is_video = source.suffix.lower() in VIDEO_AUDIO_INPUT_EXTENSIONS
    source_is_audio = source.suffix.lower() in AUDIO_INPUT_EXTENSIONS
    should_process = (
        rules.enabled
        and (
            (source_is_audio and rules.handles_audio)
            or (source_is_video and rules.handles_video)
        )
    )
    extension = rules.output_format.lower().lstrip(".") if should_process else original_extension

    if not should_process:
        return source, extension, None

    ffmpeg_path = find_ffmpeg()

    if not ffmpeg_path:
        raise RuntimeError("Media engine unavailable for audio processing.")

    temp_path = _temp_output_path(extension)
    convert_audio(
        ffmpeg_path=ffmpeg_path,
        input_file=source,
        output_file=temp_path,
        output_format=extension,
        quality_preset=rules.quality_preset,
    )
    return temp_path, extension, temp_path


def _final_output_path(
    source: Path,
    processed_path: Path,
    media_type: str,
    extension: str,
    settings: WatchSettings,
    state: WatchSessionState,
) -> Path:
    size = processed_path.stat().st_size
    base_dir = state.reserve_base_dir(settings.output_folder, size)
    sort_dir = _sort_relative_dir(media_type, extension, settings.sorting)
    rename_base_dir = base_dir / sort_dir
    relative_name = state.next_relative_path(source, extension, rename_base_dir)
    target_dir = rename_base_dir / relative_name.parent
    final_extension = relative_name.suffix.lower().lstrip(".")
    stem = relative_name.stem if final_extension else relative_name.name
    return unique_output_path(target_dir, stem, final_extension)


def _sort_relative_dir(media_type: str, extension: str, rules: SortingRules) -> Path:
    if not rules.enabled:
        return Path()

    classified = _classify_output(media_type, extension)
    if classified is None:
        return Path()

    sort_media_type, sort_extension = classified

    if sort_media_type not in rules.media_types:
        return Path()

    base = Path("__watch_output__")
    target = get_target_folder(
        base,
        sort_media_type,
        sort_extension,
        rules.folder_structure,
    )
    return target.relative_to(base)


def _sorting_handles(media_type: str, extension: str, rules: SortingRules) -> bool:
    if not rules.enabled:
        return False

    classified = _classify_output(media_type, extension)
    if classified is None:
        return False

    sort_media_type, _sort_extension = classified
    return sort_media_type in rules.media_types


def _classify_output(media_type: str, extension: str) -> tuple[str, str] | None:
    extension = extension.lower().lstrip(".")

    if extension:
        classified = classify_file(Path(f"file.{extension}"))
        if classified is not None:
            return classified

    folder = SORT_MEDIA_FOLDERS.get(media_type)
    if folder is None:
        return None

    return folder, extension


def _image_resize_args(rules: ImageRules):
    if rules.resize_mode == IMAGE_RESIZE_BY_WIDTH:
        return IMAGE_RESIZE_BY_WIDTH, rules.width, None, None, rules.max_bytes

    if rules.resize_mode == IMAGE_RESIZE_BY_HEIGHT:
        return IMAGE_RESIZE_BY_HEIGHT, None, rules.height, None, rules.max_bytes

    if rules.resize_mode == IMAGE_RESIZE_EXACT:
        return IMAGE_RESIZE_EXACT, rules.width, rules.height, None, rules.max_bytes

    if rules.resize_mode == IMAGE_RESIZE_PERCENT:
        return IMAGE_RESIZE_PERCENT, None, None, rules.percentage, rules.max_bytes

    return IMAGE_RESIZE_NONE, None, None, None, rules.max_bytes


def _video_resize_args(rules: VideoRules):
    if rules.resize_mode == VIDEO_RESIZE_PRESET:
        return VIDEO_RESIZE_PRESET, rules.preset_resolution, None, None, None, None

    if rules.resize_mode == VIDEO_RESIZE_CUSTOM:
        return VIDEO_RESIZE_CUSTOM, rules.preset_resolution, rules.width, rules.height, None, None

    if rules.resize_mode == VIDEO_RESIZE_PERCENT:
        return VIDEO_RESIZE_PERCENT, rules.preset_resolution, None, None, rules.percentage, None

    return VIDEO_RESIZE_NONE, rules.preset_resolution, None, None, None, rules.target_bytes


def _iter_candidate_files(settings: WatchSettings) -> list[Path]:
    if not settings.input_folder.exists():
        return []

    paths = settings.input_folder.rglob("*") if settings.include_subfolders else settings.input_folder.iterdir()

    return [
        path
        for path in paths
        if path.is_file() and not _should_ignore_path(path, settings)
    ]


def _should_ignore_path(path: Path, settings: WatchSettings) -> bool:
    if not path:
        return True

    try:
        path = Path(path)
    except TypeError:
        return True

    name = path.name

    if not name:
        return True

    lowered = name.lower()

    if lowered.startswith(".") or lowered.startswith("~"):
        return True

    if path.suffix.lower() in TEMP_SUFFIXES or any(lowered.endswith(suffix) for suffix in TEMP_SUFFIXES):
        return True

    if settings.output_folder.exists() and is_inside_folder(path, settings.output_folder):
        return True

    if not settings.include_subfolders:
        try:
            if path.resolve().parent != settings.input_folder.resolve():
                return True
        except OSError:
            return True

    return False


def _media_enabled(media_type: str, settings: WatchSettings) -> bool:
    has_file_operation = settings.renaming.enabled or settings.batch.enabled

    if media_type == MEDIA_IMAGE:
        return settings.image.enabled or _sorting_handles(MEDIA_IMAGE, "", settings.sorting) or has_file_operation

    if media_type == MEDIA_VIDEO:
        return settings.video.enabled or _sorting_handles(MEDIA_VIDEO, "", settings.sorting) or has_file_operation

    if media_type == MEDIA_AUDIO:
        return settings.audio.handles_audio or settings.audio.handles_video or _sorting_handles(MEDIA_AUDIO, "", settings.sorting) or has_file_operation

    return False


def _validate_settings(settings: WatchSettings):
    if not settings.input_folder.is_dir():
        raise ValueError("Choose a valid input folder.")

    if not settings.output_folder:
        raise ValueError("Choose a valid output folder.")

    if settings.input_folder.resolve() == settings.output_folder.resolve():
        raise ValueError("Input and output folders must be different.")

    settings.output_folder.mkdir(parents=True, exist_ok=True)


def _normalize_settings(settings: WatchSettings) -> WatchSettings:
    return WatchSettings(
        input_folder=Path(settings.input_folder),
        output_folder=Path(settings.output_folder),
        include_subfolders=settings.include_subfolders,
        process_existing=settings.process_existing,
        image=settings.image,
        video=settings.video,
        audio=settings.audio,
        sorting=settings.sorting,
        renaming=settings.renaming,
        batch=settings.batch,
        stable_interval_seconds=settings.stable_interval_seconds,
        stable_timeout_seconds=settings.stable_timeout_seconds,
    )


def _temp_output_path(extension: str) -> Path:
    extension = extension.lower().lstrip(".")
    handle, path = tempfile.mkstemp(prefix="zdbatcher_watch_", suffix=f".{extension}")
    try:
        import os

        os.close(handle)
    except OSError:
        pass
    return Path(path)


def _path_key(path: Path) -> str:
    try:
        return str(path.resolve()).lower()
    except OSError:
        return str(path.absolute()).lower()
