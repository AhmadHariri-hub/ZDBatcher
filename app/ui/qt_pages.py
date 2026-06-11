import queue
import threading
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QDoubleValidator, QIntValidator
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.config import SUPPORTED_INPUTS
from app.core.audio_converter import (
    AUDIO_INPUT_EXTENSIONS,
    FILTER_AUDIO_AND_VIDEO,
    FILTER_AUDIO_ONLY,
    FILTER_VIDEO_ONLY,
    INPUT_TYPE_FILTERS,
    OUTPUT_AUDIO_FORMATS,
    QUALITY_BALANCED as AUDIO_QUALITY_BALANCED,
    QUALITY_PRESETS as AUDIO_QUALITY_PRESETS,
    SUPPORTED_AUDIO_INPUTS,
    convert_audio,
    describe_quality as describe_audio_quality,
    get_audio_inputs,
    input_filter_includes_video,
)
from app.core.batcher import (
    BATCH_BY_COUNT,
    BATCH_BY_SIZE,
    BATCH_METHODS,
    batch_folder_path,
    copy_file_to_batch_folder,
    format_bytes,
    get_batch_folder,
    get_batch_folder_by_index,
    move_file_to_batch_folder,
    parse_batch_size,
    parse_folder_size_mb,
    remove_files_inside_output_folder,
    should_start_new_size_batch,
)
from app.core.file_sorter import (
    FOLDER_STRUCTURES,
    MEDIA_AUDIO,
    MEDIA_IMAGES,
    MEDIA_VIDEOS,
    MODE_COPY,
    MODE_MOVE,
    OPERATION_MODES,
    collect_sort_preview,
    sort_file,
)
from app.core.file_utils import get_supported_files, unique_output_path
from app.core.image_converter import (
    convert_image,
    get_output_formats,
    original_output_format,
    output_extension_for_format,
    safe_max_bytes,
)
from app.core.image_resizer import (
    QUALITY_BALANCED as IMAGE_RESIZE_QUALITY_BALANCED,
    RESIZE_BY_HEIGHT,
    RESIZE_BY_WIDTH,
    RESIZE_EXACT,
    RESIZE_MODES as IMAGE_RESIZE_MODES,
    RESIZE_PERCENT as IMAGE_RESIZE_PERCENT,
    resize_and_compress_image,
    parse_optional_max_bytes,
    parse_percentage as parse_image_percentage,
    parse_positive_int as parse_image_positive_int,
)
from app.core.media_engine import find_ffmpeg
from app.core.mixed_media_converter import (
    MEDIA_AUDIO as MIXED_AUDIO,
    MEDIA_FOLDER_NAMES,
    MEDIA_IMAGE,
    MEDIA_LABELS,
    MEDIA_VIDEO,
    ORG_MEDIA_FOLDERS,
    ORG_ONE_FOLDER,
    OUTPUT_ORGANIZATION_OPTIONS,
    collect_media_files,
    convert_mixed_file,
    media_original_output_extension,
    media_output_extension,
    resize_mixed_file,
)
from app.core.renamer import (
    FILE_FILTER_ALL,
    FILE_FILTERS,
    NUMBERING_INTERNAL,
    NUMBERING_SOURCES,
    RENAME_GLOBAL,
    RENAME_MODES,
    SORT_MODES,
    SORT_NAME_ASC,
    build_rename_plan,
    copy_rename_plan_item,
    get_renamable_files,
    parse_padding,
    parse_starting_number,
    preview_names,
    sort_files,
)
from app.core.video_converter import (
    GIF_FPS_OPTIONS,
    GIF_FPS_ORIGINAL,
    GIF_WIDTH_CUSTOM,
    GIF_WIDTH_KEEP,
    GIF_WIDTH_OPTIONS,
    OUTPUT_VIDEO_FORMATS,
    QUALITY_BALANCED as VIDEO_QUALITY_BALANCED,
    RESIZE_KEEP,
    SUPPORTED_VIDEO_INPUTS,
    convert_video,
    get_video_files,
)
from app.core.video_resizer import (
    PRESET_1080,
    PRESET_RESOLUTIONS,
    QUALITY_BALANCED as VIDEO_RESIZE_QUALITY_BALANCED,
    RESIZE_CUSTOM as VIDEO_RESIZE_CUSTOM,
    RESIZE_MODES as VIDEO_RESIZE_MODES,
    RESIZE_PERCENT as VIDEO_RESIZE_PERCENT,
    RESIZE_PRESET as VIDEO_RESIZE_PRESET,
    original_video_output_format,
    parse_optional_target_bytes,
    parse_percentage as parse_video_percentage,
    parse_positive_int as parse_video_positive_int,
    resize_video,
)
from app.ui.qt_theme import Theme
from app.ui.qt_widgets import (
    AppCheckBox as QCheckBox,
    AppComboBox,
    AppLineEdit,
    MODE_BATCH,
    MODE_SINGLE,
    Card,
    LogView,
    PathPicker,
    SegmentedControl,
    ask_confirm,
    file_filter,
    make_button,
    make_label,
    make_temp_output_path,
    save_temp_output,
    set_role,
    show_message,
)
from app.ui.tool_labels import (
    BATCH_METHOD,
    CUSTOM_GIF_WIDTH,
    EXTENSIONS,
    FOLDER_STRUCTURE,
    GIF_FPS,
    GIF_WIDTH,
    HEIGHT,
    INPUT_FILTER,
    MAX_FOLDER_SIZE,
    MAX_MB,
    MEDIA_TYPES,
    OUTPUT_FORMAT,
    PADDING,
    PERCENTAGE,
    PRESET,
    QUALITY,
    RENAMING_MODE,
    RESIZE,
    RESIZE_MODE,
    SIZE_LIMIT,
    STARTING_NUMBER,
    TARGET_MB,
    TARGET_SIZE,
    WIDTH,
    NUMBERING_SOURCE,
    PREFIX,
)


PLACEHOLDER_INPUT = "No input selected"
PAGE_MARGIN = 24
SCROLLBAR_GUTTER = 12
FORM_FIELD_MAX_WIDTH = 380
FORM_FIELD_MIN_WIDTH = 220

BATCH_FILTER_IMAGES = "Images only"
BATCH_FILTER_VIDEOS = "Videos / GIFs only"
BATCH_FILTER_AUDIO = "Audio only"
BATCH_FILTER_SUPPORTED_MEDIA = "All supported media"
BATCH_FILTER_ALL_FILES = "All files"
BATCH_FILE_FILTERS = [
    BATCH_FILTER_IMAGES,
    BATCH_FILTER_VIDEOS,
    BATCH_FILTER_AUDIO,
    BATCH_FILTER_SUPPORTED_MEDIA,
    BATCH_FILTER_ALL_FILES,
]


def combo(items, current=None) -> AppComboBox:
    box = AppComboBox()
    box.addItems([str(item) for item in items])
    if current is not None:
        index = box.findText(str(current))
        if index >= 0:
            box.setCurrentIndex(index)
    return box


def line(value: str = "", *, integer=False, decimal=False) -> QLineEdit:
    edit = AppLineEdit(value)
    edit.setMinimumHeight(40)
    if integer:
        validator = QIntValidator(0, 999999)
        edit.setValidator(validator)
    elif decimal:
        validator = QDoubleValidator(0.0, 999999.0, 3)
        validator.setNotation(QDoubleValidator.StandardNotation)
        edit.setValidator(validator)
    return edit


def polish_form_widget(widget: QWidget):
    if isinstance(widget, (AppComboBox, QLineEdit)):
        widget.setMinimumWidth(FORM_FIELD_MIN_WIDTH)
        widget.setMaximumWidth(FORM_FIELD_MAX_WIDTH)
        widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)


def add_grid_row(grid: QGridLayout, row: int, label: str, widget: QWidget, hint: str = ""):
    label_widget = make_label(label)
    label_widget.setStyleSheet("font-weight: 700;")
    grid.addWidget(label_widget, row, 0, alignment=Qt.AlignTop)
    polish_form_widget(widget)
    alignment = Qt.AlignLeft | Qt.AlignTop if isinstance(widget, (AppComboBox, QLineEdit, QCheckBox)) else Qt.AlignTop
    grid.addWidget(widget, row, 1, alignment=alignment)
    if hint:
        hint_label = make_label(hint, muted=True)
        grid.addWidget(hint_label, row + 1, 1)
        return row + 2
    return row + 1


def grid_row_widgets(grid: QGridLayout, row: int) -> list[QWidget]:
    widgets = []
    for column in (0, 1):
        item = grid.itemAtPosition(row, column)
        if item and item.widget():
            widgets.append(item.widget())
    return widgets


def make_grid(parent: QWidget) -> QGridLayout:
    grid = QGridLayout(parent)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(22)
    grid.setVerticalSpacing(14)
    grid.setColumnMinimumWidth(0, 170)
    grid.setColumnStretch(0, 0)
    grid.setColumnStretch(1, 1)
    return grid


def positive_mb(value: str, label: str) -> int:
    parsed = float(value.strip())
    if parsed <= 0:
        raise ValueError(f"{label} must be greater than zero.")
    return max(1, int(parsed * 1_000_000) - 1024)


class BatchOptions(Card):
    def __init__(self, *, count_label="Files per folder", count_default="40", size_default="100"):
        super().__init__("Optional output batches", "Split finished files into smaller output folders.")
        self.enabled = QCheckBox("Create output batches")
        self.method = combo(BATCH_METHODS, BATCH_BY_COUNT)
        self.count = line(count_default, integer=True)
        self.size_mb = line(size_default, decimal=True)

        self.body_layout.addWidget(self.enabled)
        grid_holder = QWidget()
        self.grid = make_grid(grid_holder)
        row = 0
        row = add_grid_row(self.grid, row, BATCH_METHOD, self.method)
        row = add_grid_row(self.grid, row, count_label, self.count)
        add_grid_row(self.grid, row, MAX_FOLDER_SIZE, self.size_mb, "Size is measured from finished output files, in MB.")
        self.body_layout.addWidget(grid_holder)

        self.enabled.toggled.connect(self._sync)
        self.method.currentTextChanged.connect(lambda _text: self._sync())
        self._sync()

    def _sync(self):
        enabled = self.enabled.isChecked()
        self.method.setEnabled(enabled)
        by_count = self.method.currentText() == BATCH_BY_COUNT
        self.count.setEnabled(enabled and by_count)
        self.size_mb.setEnabled(enabled and not by_count)

    def snapshot(self) -> dict:
        enabled = self.enabled.isChecked()
        method = self.method.currentText()
        batch_size = None
        max_bytes = None
        if enabled and method == BATCH_BY_COUNT:
            batch_size = parse_batch_size(self.count.text())
        elif enabled:
            max_bytes = parse_folder_size_mb(self.size_mb.text())
        return {
            "enabled": enabled,
            "method": method,
            "batch_size": batch_size,
            "max_bytes": max_bytes,
            "size_text": self.size_mb.text(),
        }


class ToolPage(QWidget):
    def __init__(self, title: str, subtitle: str, theme_provider):
        super().__init__()
        self.title = title
        self.subtitle = subtitle
        self.theme_provider = theme_provider
        self.message_queue = queue.Queue()
        self.worker_running = False
        self.action_button: QPushButton | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("ScrollContent")
        scroll_layout = QVBoxLayout(self.scroll_content)
        scroll_layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, 16)
        scroll_layout.setSpacing(0)

        self.content = QWidget()
        self.content.setObjectName("ContentColumn")
        self.content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(16)
        scroll_layout.addWidget(self.content)
        scroll_layout.addStretch(1)
        self.scroll.setWidget(self.scroll_content)
        splitter.addWidget(self.scroll)

        self._add_header()

        self.action_panel = QFrame()
        self.action_panel.setObjectName("ActionPanel")
        action_layout = QVBoxLayout(self.action_panel)
        action_layout.setContentsMargins(18, 16, 18, 16)
        action_layout.setSpacing(10)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(12)
        status_text = QVBoxLayout()
        status_text.setContentsMargins(0, 0, 0, 0)
        self.status_label = make_label("Ready", role="statusTitle")
        self.status_subtitle = make_label("Choose settings, then start.", muted=True)
        status_text.addWidget(self.status_label)
        status_text.addWidget(self.status_subtitle)
        status_row.addLayout(status_text, 1)
        self.action_slot = QHBoxLayout()
        self.action_slot.setContentsMargins(0, 0, 0, 0)
        status_row.addLayout(self.action_slot)
        action_layout.addLayout(status_row)

        self.progress = QFrame()
        self.progress_bar = None
        from PySide6.QtWidgets import QProgressBar

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        action_layout.addWidget(self.progress_bar)

        self.log = LogView()
        action_layout.addWidget(self.log)
        action_shell = QWidget()
        action_shell.setObjectName("PageContent")
        action_shell_layout = QVBoxLayout(action_shell)
        action_shell_layout.setContentsMargins(PAGE_MARGIN, 0, PAGE_MARGIN + SCROLLBAR_GUTTER, PAGE_MARGIN)
        action_shell_layout.setSpacing(0)
        self.action_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        action_shell_layout.addWidget(self.action_panel)
        splitter.addWidget(action_shell)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([700, 300])

        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self._process_queue)
        self.timer.start()

    def _add_header(self):
        header = QWidget()
        header.setObjectName("PageHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 2)
        header_layout.setSpacing(4)
        eyebrow = make_label("TOOL", role="eyebrow")
        title = make_label(self.title, role="pageTitle")
        subtitle = make_label(self.subtitle, muted=True)
        header_layout.addWidget(eyebrow)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        self.content_layout.addWidget(header)

    def theme(self) -> Theme:
        return self.theme_provider()

    def add_action(self, text: str, callback):
        self.action_button = make_button(text, "primary")
        self.action_button.setMinimumWidth(180)
        self.action_button.clicked.connect(callback)
        self.action_slot.addWidget(self.action_button)

    def set_busy(self, busy: bool):
        self.worker_running = busy
        if self.action_button is not None:
            self.action_button.setEnabled(not busy)

    def post(self, kind: str, *payload):
        self.message_queue.put((kind, *payload))

    def start_worker(self, snapshot: dict):
        if self.worker_running:
            return
        self.set_busy(True)
        self.log.clear()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.status_label.setText("Preparing")
        self.status_subtitle.setText("Checking files and settings.")
        threading.Thread(target=self._worker_entry, args=(snapshot,), daemon=True).start()

    def _worker_entry(self, snapshot: dict):
        try:
            self.run_task(snapshot)
        except Exception as exc:
            self.post("error", str(exc))

    def run_task(self, snapshot: dict):
        raise NotImplementedError

    def _process_queue(self):
        logs = []
        try:
            while True:
                item = self.message_queue.get_nowait()
                kind = item[0]
                if kind == "log":
                    logs.append((item[1], item[2] if len(item) > 2 else ""))
                    continue
                self._handle_event(item)
        except queue.Empty:
            pass
        if logs:
            self.log.append_lines(logs, self.theme())

    def _handle_event(self, item):
        kind = item[0]
        if kind == "status":
            self.status_label.setText(item[1])
            if len(item) > 2:
                self.status_subtitle.setText(item[2])
        elif kind == "progress":
            self.progress_bar.setRange(0, max(1, item[2]))
            self.progress_bar.setValue(item[1])
        elif kind == "done":
            self.set_busy(False)
            self.status_label.setText("Finished")
            self.status_subtitle.setText(item[2] if len(item) > 2 else "Operation complete.")
            show_message(self, "Finished", item[1], self.theme())
        elif kind == "single_done":
            self.set_busy(False)
            self.status_label.setText("Ready to save")
            self.status_subtitle.setText("Choose where to save the converted file.")
            save_temp_output(self, Path(item[1]), item[2], self.theme(), self.log_line)
        elif kind == "error":
            self.set_busy(False)
            self.status_label.setText("Error")
            self.status_subtitle.setText("Fix the issue shown below, then try again.")
            self.log.append_line(item[1], "err", self.theme())
            show_message(self, "Error", item[1], self.theme(), "error")

    def log_line(self, text: str, tag: str = ""):
        self.log.append_line(text, tag, self.theme())


def update_size_batch(out_path: Path, state: dict, output_dir: Path, max_batch_bytes: int) -> Path:
    processed_size = out_path.stat().st_size
    if should_start_new_size_batch(
        current_batch_size=state["size"],
        next_file_size=processed_size,
        max_batch_bytes=max_batch_bytes,
        current_batch_file_count=state["count"],
    ):
        state["index"] += 1
        new_batch_dir = get_batch_folder_by_index(output_dir, state["index"])
        out_path = move_file_to_batch_folder(out_path, new_batch_dir)
        processed_size = out_path.stat().st_size
        state["size"] = 0
        state["count"] = 0
    state["size"] += processed_size
    state["count"] += 1
    return out_path


class ImageConversionPage(ToolPage):
    def __init__(self, theme_provider):
        super().__init__(
            "Image Conversion",
            "Convert image folders or one image at a time while keeping output handling simple.",
            theme_provider,
        )
        self.mode = SegmentedControl([(MODE_BATCH, "Batch"), (MODE_SINGLE, "Single File")], MODE_BATCH)
        self.mode.on_changed(self._sync_mode)
        self.content_layout.addWidget(self.mode)

        self.batch_input = Card("Input and output", "Choose a source folder and where converted images should go.")
        self.input_folder = PathPicker("Input folder", "Folder containing source images.")
        self.output_folder = PathPicker("Output folder", "Folder for converted images.")
        self.include_subfolders = QCheckBox("Include subfolders")
        self.batch_input.body_layout.addWidget(self.input_folder)
        self.batch_input.body_layout.addWidget(self.output_folder)
        self.batch_input.body_layout.addWidget(self.include_subfolders)
        self.content_layout.addWidget(self.batch_input)

        self.single_input = Card("Single file", "Convert one image, then choose where to save it.")
        self.input_file = PathPicker("Input image", "One source image file.", drop_kind="file", supported_extensions=SUPPORTED_INPUTS)
        self.single_input.body_layout.addWidget(self.input_file)
        self.content_layout.addWidget(self.single_input)

        self.settings = Card("Settings", "Choose the output image format.")
        holder = QWidget()
        grid = make_grid(holder)
        self.output_format = combo(get_output_formats(), "jpg")
        add_grid_row(grid, 0, OUTPUT_FORMAT, self.output_format)
        self.settings.body_layout.addWidget(holder)
        self.content_layout.addWidget(self.settings)

        self.batch_options = BatchOptions(count_label="Images per folder")
        self.content_layout.addWidget(self.batch_options)
        self.content_layout.addStretch(1)

        self.input_folder.button.clicked.connect(self._choose_input_folder)
        self.output_folder.button.clicked.connect(self._choose_output_folder)
        self.input_file.button.clicked.connect(self._choose_input_file)
        self.add_action("Convert Images", self._start)
        self._sync_mode(MODE_BATCH)

    def _sync_mode(self, mode: str):
        single = mode == MODE_SINGLE
        self.batch_input.setVisible(not single)
        self.batch_options.setVisible(not single)
        self.single_input.setVisible(single)
        if self.action_button:
            self.action_button.setText("Convert Image" if single else "Convert Images")

    def _choose_input_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose input folder")
        if folder:
            self.input_folder.set_path(folder)
            if not self.output_folder.path():
                path = Path(folder)
                self.output_folder.set_path(path.parent / f"{path.name}_output")

    def _choose_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if folder:
            self.output_folder.set_path(folder)

    def _choose_input_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose input image",
            "",
            f"{file_filter('Images', SUPPORTED_INPUTS)};;All files (*.*)",
        )
        if path:
            self.input_file.set_path(path)

    def _start(self):
        try:
            snapshot = {
                "mode": self.mode.value(),
                "input_folder": self.input_folder.path(),
                "output_folder": self.output_folder.path(),
                "input_file": self.input_file.path(),
                "include_subfolders": self.include_subfolders.isChecked(),
                "output_format": self.output_format.currentText().lower(),
                "batch": self.batch_options.snapshot(),
            }
        except ValueError as exc:
            show_message(self, "Error", str(exc), self.theme(), "error")
            return
        self.start_worker(snapshot)

    def run_task(self, s: dict):
        if s["mode"] == MODE_SINGLE:
            input_file = Path(s["input_file"])
            if not input_file.is_file():
                self.post("error", "Choose a valid input image.")
                return
            output_format = s["output_format"]
            temp_path = make_temp_output_path(output_extension_for_format(output_format))
            self.post("progress", 0, 1)
            self.post("status", "Converting image", input_file.name)
            convert_image(input_file, temp_path, output_format)
            self.post("progress", 1, 1)
            self.post("single_done", str(temp_path), f"{input_file.stem}.{temp_path.suffix.lstrip('.')}")
            return

        input_dir = Path(s["input_folder"])
        output_dir = Path(s["output_folder"])
        if not input_dir.is_dir():
            self.post("error", "Choose a valid input folder.")
            return
        if not s["output_folder"]:
            self.post("error", "Choose a valid output folder.")
            return
        output_dir.mkdir(parents=True, exist_ok=True)
        files = get_supported_files(input_dir, s["include_subfolders"])
        if not files:
            self.post("error", "No supported images found in that folder.")
            return

        self.post("progress", 0, len(files))
        self.post("status", "Converting images", f"0 of {len(files)} files converted.")
        self.post("log", f"Found {len(files)} image(s)", "info")
        self.post("log", f"Input   : {input_dir}", "dim")
        self.post("log", f"Output  : {output_dir}", "dim")
        self.post("log", f"Format  : {s['output_format'].upper()}", "dim")

        state = {"size": 0, "count": 0, "index": 1}
        success = 0
        failed = []
        ext = output_extension_for_format(s["output_format"])
        for idx, file in enumerate(files, start=1):
            self.post("status", f"Converting {idx}/{len(files)}", file.name)
            out_path = None
            try:
                if s["batch"]["enabled"] and s["batch"]["method"] == BATCH_BY_COUNT:
                    target_dir = get_batch_folder(output_dir, idx, s["batch"]["batch_size"])
                elif s["batch"]["enabled"]:
                    target_dir = get_batch_folder_by_index(output_dir, state["index"])
                else:
                    target_dir = output_dir
                out_path = unique_output_path(target_dir, file.stem, ext)
                convert_image(file, out_path, s["output_format"])
                if s["batch"]["enabled"] and s["batch"]["method"] == BATCH_BY_SIZE:
                    out_path = update_size_batch(out_path, state, output_dir, s["batch"]["max_bytes"])
                self.post("log", f"OK   {file.name} -> {out_path.name}", "ok")
                success += 1
            except Exception as exc:
                failed.append(file.name)
                if out_path and out_path.exists():
                    out_path.unlink()
                self.post("log", f"FAIL {file.name}: {exc}", "err")
            self.post("progress", idx, len(files))
        message = f"Converted {success} of {len(files)} image(s)."
        if failed:
            message += f"\nFailed: {len(failed)}"
        self.post("done", message, "Image conversion complete. Check the output folder.")


class ImageResizerPage(ToolPage):
    def __init__(self, theme_provider):
        super().__init__(
            "Image Resizer",
            "Resize, compress, and optionally target a max size for image batches or a single file.",
            theme_provider,
        )
        self.mode = SegmentedControl([(MODE_BATCH, "Batch"), (MODE_SINGLE, "Single File")], MODE_BATCH)
        self.mode.on_changed(self._sync_mode)
        self.content_layout.addWidget(self.mode)

        self.batch_input = Card("Input and output")
        self.input_folder = PathPicker("Input folder", "Folder containing source images.")
        self.output_folder = PathPicker("Output folder", "Folder for resized images.")
        self.include_subfolders = QCheckBox("Include subfolders")
        self.batch_input.body_layout.addWidget(self.input_folder)
        self.batch_input.body_layout.addWidget(self.output_folder)
        self.batch_input.body_layout.addWidget(self.include_subfolders)
        self.content_layout.addWidget(self.batch_input)

        self.single_input = Card("Single file")
        self.input_file = PathPicker("Input image", "One source image file.", drop_kind="file", supported_extensions=SUPPORTED_INPUTS)
        self.single_input.body_layout.addWidget(self.input_file)
        self.content_layout.addWidget(self.single_input)

        self.settings = Card("Resize and compression")
        holder = QWidget()
        grid = make_grid(holder)
        self.resize_mode = combo(IMAGE_RESIZE_MODES, RESIZE_BY_WIDTH)
        self.width = line("1200", integer=True)
        self.height = line("800", integer=True)
        self.percentage = line("50", decimal=True)
        self.max_size_enabled = QCheckBox("Target max file size")
        self.max_mb = line("3", decimal=True)
        row = 0
        row = add_grid_row(grid, row, RESIZE_MODE, self.resize_mode)
        row = add_grid_row(grid, row, WIDTH, self.width)
        row = add_grid_row(grid, row, HEIGHT, self.height)
        row = add_grid_row(grid, row, PERCENTAGE, self.percentage)
        row = add_grid_row(grid, row, SIZE_LIMIT, self.max_size_enabled)
        add_grid_row(grid, row, MAX_MB, self.max_mb)
        self.settings.body_layout.addWidget(holder)
        self.content_layout.addWidget(self.settings)

        self.preserve_filename = QCheckBox("Preserve source file names")
        self.preserve_filename.setChecked(True)
        self.settings.body_layout.addWidget(self.preserve_filename)

        self.batch_options = BatchOptions(count_label="Images per folder")
        self.content_layout.addWidget(self.batch_options)
        self.content_layout.addStretch(1)

        self.input_folder.button.clicked.connect(self._choose_input_folder)
        self.output_folder.button.clicked.connect(self._choose_output_folder)
        self.input_file.button.clicked.connect(self._choose_input_file)
        self.resize_mode.currentTextChanged.connect(lambda _text: self._sync_resize_fields())
        self.max_size_enabled.toggled.connect(lambda _checked: self._sync_resize_fields())
        self.add_action("Resize Images", self._start)
        self._sync_mode(MODE_BATCH)
        self._sync_resize_fields()

    def _sync_mode(self, mode: str):
        single = mode == MODE_SINGLE
        self.batch_input.setVisible(not single)
        self.batch_options.setVisible(not single)
        self.preserve_filename.setVisible(not single)
        self.single_input.setVisible(single)
        if self.action_button:
            self.action_button.setText("Resize Image" if single else "Resize Images")

    def _sync_resize_fields(self):
        mode = self.resize_mode.currentText()
        self.width.setEnabled(mode in {RESIZE_BY_WIDTH, RESIZE_EXACT})
        self.height.setEnabled(mode in {RESIZE_BY_HEIGHT, RESIZE_EXACT})
        self.percentage.setEnabled(mode == IMAGE_RESIZE_PERCENT)
        self.max_mb.setEnabled(self.max_size_enabled.isChecked())

    def _choose_input_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose input folder")
        if folder:
            self.input_folder.set_path(folder)
            if not self.output_folder.path():
                path = Path(folder)
                self.output_folder.set_path(path.parent / f"{path.name}_resized")

    def _choose_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if folder:
            self.output_folder.set_path(folder)

    def _choose_input_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose input image",
            "",
            f"{file_filter('Images', SUPPORTED_INPUTS)};;All files (*.*)",
        )
        if path:
            self.input_file.set_path(path)

    def _resize_snapshot(self) -> dict:
        mode = self.resize_mode.currentText()
        return {
            "resize_mode": mode,
            "width": parse_image_positive_int(self.width.text(), WIDTH) if mode in {RESIZE_BY_WIDTH, RESIZE_EXACT} else None,
            "height": parse_image_positive_int(self.height.text(), HEIGHT) if mode in {RESIZE_BY_HEIGHT, RESIZE_EXACT} else None,
            "percentage": parse_image_percentage(self.percentage.text()) if mode == IMAGE_RESIZE_PERCENT else None,
            "max_bytes": parse_optional_max_bytes(self.max_mb.text()) if self.max_size_enabled.isChecked() else None,
        }

    def _start(self):
        try:
            snap = self._resize_snapshot()
            snap.update({
                "mode": self.mode.value(),
                "input_folder": self.input_folder.path(),
                "output_folder": self.output_folder.path(),
                "input_file": self.input_file.path(),
                "include_subfolders": self.include_subfolders.isChecked(),
                "preserve_filename": self.preserve_filename.isChecked(),
                "batch": self.batch_options.snapshot(),
            })
        except ValueError as exc:
            show_message(self, "Error", str(exc), self.theme(), "error")
            return
        self.start_worker(snap)

    def run_task(self, s: dict):
        if s["mode"] == MODE_SINGLE:
            input_file = Path(s["input_file"])
            if not input_file.is_file():
                self.post("error", "Choose a valid input image.")
                return
            output_format = original_output_format(input_file)
            temp_path = make_temp_output_path(output_extension_for_format(output_format))
            self.post("progress", 0, 1)
            result = resize_and_compress_image(input_file, temp_path, output_format, s["resize_mode"], s["width"], s["height"], s["percentage"], IMAGE_RESIZE_QUALITY_BALANCED, s["max_bytes"])
            self.post("log", f"{result.original_dimensions[0]}x{result.original_dimensions[1]} -> {result.output_dimensions[0]}x{result.output_dimensions[1]}", "info")
            self.post("progress", 1, 1)
            self.post("single_done", str(temp_path), f"{input_file.stem}.{temp_path.suffix.lstrip('.')}")
            return

        input_dir = Path(s["input_folder"])
        output_dir = Path(s["output_folder"])
        if not input_dir.is_dir():
            self.post("error", "Choose a valid input folder.")
            return
        if not s["output_folder"]:
            self.post("error", "Choose a valid output folder.")
            return
        output_dir.mkdir(parents=True, exist_ok=True)
        files = get_supported_files(input_dir, s["include_subfolders"])
        if not files:
            self.post("error", "No supported images found in that folder.")
            return
        self.post("progress", 0, len(files))
        self.post("log", f"Found {len(files)} image(s)", "info")
        state = {"size": 0, "count": 0, "index": 1}
        success = 0
        for idx, file in enumerate(files, start=1):
            self.post("status", f"Resizing {idx}/{len(files)}", file.name)
            out_path = None
            try:
                if s["batch"]["enabled"] and s["batch"]["method"] == BATCH_BY_COUNT:
                    target_dir = get_batch_folder(output_dir, idx, s["batch"]["batch_size"])
                elif s["batch"]["enabled"]:
                    target_dir = get_batch_folder_by_index(output_dir, state["index"])
                else:
                    target_dir = output_dir
                stem = file.stem if s["preserve_filename"] else str(idx)
                output_format = original_output_format(file)
                out_path = unique_output_path(target_dir, stem, output_extension_for_format(output_format))
                result = resize_and_compress_image(file, out_path, output_format, s["resize_mode"], s["width"], s["height"], s["percentage"], IMAGE_RESIZE_QUALITY_BALANCED, s["max_bytes"])
                if s["batch"]["enabled"] and s["batch"]["method"] == BATCH_BY_SIZE:
                    out_path = update_size_batch(out_path, state, output_dir, s["batch"]["max_bytes"])
                self.post("log", f"OK   {file.name} -> {out_path.name} ({format_bytes(result.output_size)})", "ok")
                success += 1
            except Exception as exc:
                if out_path and out_path.exists():
                    out_path.unlink()
                self.post("log", f"FAIL {file.name}: {exc}", "err")
            self.post("progress", idx, len(files))
        self.post("done", f"Processed {success} of {len(files)} image(s).", "Image resize complete. Check the output folder.")


class VideoConverterPage(ToolPage):
    def __init__(self, theme_provider):
        super().__init__("Video Converter", "Convert videos and GIFs from one format to another with FFmpeg.", theme_provider)
        self.mode = SegmentedControl([(MODE_BATCH, "Batch"), (MODE_SINGLE, "Single File")], MODE_BATCH)
        self.mode.on_changed(self._sync_mode)
        self.content_layout.addWidget(self.mode)

        self.engine = make_label("Video engine ready" if find_ffmpeg() else "Video engine unavailable", role="eyebrow")
        self.content_layout.addWidget(self.engine)

        self.batch_input = Card("Input and output")
        self.input_folder = PathPicker("Input folder", "Folder containing videos or GIFs.")
        self.output_folder = PathPicker("Output folder", "Folder for converted videos.")
        self.include_subfolders = QCheckBox("Include subfolders")
        self.batch_input.body_layout.addWidget(self.input_folder)
        self.batch_input.body_layout.addWidget(self.output_folder)
        self.batch_input.body_layout.addWidget(self.include_subfolders)
        self.content_layout.addWidget(self.batch_input)

        self.single_input = Card("Single file")
        self.input_file = PathPicker("Input video", "One source video or GIF file.", drop_kind="file", supported_extensions=SUPPORTED_VIDEO_INPUTS)
        self.single_input.body_layout.addWidget(self.input_file)
        self.content_layout.addWidget(self.single_input)

        self.settings = Card("Settings")
        holder = QWidget()
        grid = make_grid(holder)
        self.output_format = combo(OUTPUT_VIDEO_FORMATS, "mp4")
        self.gif_fps = combo(GIF_FPS_OPTIONS, GIF_FPS_ORIGINAL)
        self.gif_width = combo(GIF_WIDTH_OPTIONS, GIF_WIDTH_KEEP)
        self.gif_custom_width = line("", integer=True)
        row = 0
        row = add_grid_row(grid, row, OUTPUT_FORMAT, self.output_format)
        gif_fps_row = row
        row = add_grid_row(grid, row, GIF_FPS, self.gif_fps)
        gif_width_row = row
        row = add_grid_row(grid, row, GIF_WIDTH, self.gif_width)
        gif_custom_width_row = row
        add_grid_row(grid, row, CUSTOM_GIF_WIDTH, self.gif_custom_width)
        self.gif_rows = [
            grid_row_widgets(grid, gif_fps_row),
            grid_row_widgets(grid, gif_width_row),
        ]
        self.gif_custom_width_row = grid_row_widgets(grid, gif_custom_width_row)
        self.settings.body_layout.addWidget(holder)
        self.preserve_filename = QCheckBox("Preserve source file names")
        self.preserve_filename.setChecked(True)
        self.settings.body_layout.addWidget(self.preserve_filename)
        self.content_layout.addWidget(self.settings)

        self.batch_options = BatchOptions(count_label="Videos per folder", count_default="20", size_default="1000")
        self.content_layout.addWidget(self.batch_options)
        self.content_layout.addStretch(1)

        self.input_folder.button.clicked.connect(self._choose_input_folder)
        self.output_folder.button.clicked.connect(self._choose_output_folder)
        self.input_file.button.clicked.connect(self._choose_input_file)
        self.output_format.currentTextChanged.connect(lambda _text: self._sync_format())
        self.gif_width.currentTextChanged.connect(lambda _text: self._sync_format())
        self.add_action("Convert Videos", self._start)
        self._sync_mode(MODE_BATCH)
        self._sync_format()

    def _sync_mode(self, mode: str):
        single = mode == MODE_SINGLE
        self.batch_input.setVisible(not single)
        self.batch_options.setVisible(not single)
        self.preserve_filename.setVisible(not single)
        self.single_input.setVisible(single)
        if self.action_button:
            self.action_button.setText("Convert Video" if single else "Convert Videos")

    def _sync_format(self):
        gif = self.output_format.currentText().lower() == "gif"
        custom_width = gif and self.gif_width.currentText() == GIF_WIDTH_CUSTOM
        for row in self.gif_rows:
            for widget in row:
                widget.setVisible(gif)
                widget.setEnabled(gif)
        for widget in self.gif_custom_width_row:
            widget.setVisible(custom_width)
            widget.setEnabled(custom_width)

    def _choose_input_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose input folder")
        if folder:
            self.input_folder.set_path(folder)
            if not self.output_folder.path():
                path = Path(folder)
                self.output_folder.set_path(path.parent / f"{path.name}_video_output")

    def _choose_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if folder:
            self.output_folder.set_path(folder)

    def _choose_input_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose input video", "", f"{file_filter('Videos', SUPPORTED_VIDEO_INPUTS)};;All files (*.*)")
        if path:
            self.input_file.set_path(path)

    def _gif_custom(self) -> int | None:
        if self.output_format.currentText().lower() != "gif" or self.gif_width.currentText() != GIF_WIDTH_CUSTOM:
            return None
        value = self.gif_custom_width.text().strip()
        if not value:
            raise ValueError("Custom GIF width is required.")
        parsed = int(value)
        if parsed <= 0:
            raise ValueError("Custom GIF width must be greater than zero.")
        return parsed

    def _snapshot(self) -> dict:
        return {
            "mode": self.mode.value(),
            "input_folder": self.input_folder.path(),
            "output_folder": self.output_folder.path(),
            "input_file": self.input_file.path(),
            "include_subfolders": self.include_subfolders.isChecked(),
            "output_format": self.output_format.currentText().lower(),
            "quality": VIDEO_QUALITY_BALANCED,
            "resize": RESIZE_KEEP,
            "gif_fps": self.gif_fps.currentText(),
            "gif_width": self.gif_width.currentText(),
            "gif_custom_width": self._gif_custom(),
            "preserve_filename": self.preserve_filename.isChecked(),
            "batch": self.batch_options.snapshot(),
        }

    def _start(self):
        try:
            self.start_worker(self._snapshot())
        except ValueError as exc:
            show_message(self, "Error", str(exc), self.theme(), "error")

    def run_task(self, s: dict):
        ffmpeg_path = find_ffmpeg()
        if not ffmpeg_path:
            self.post("error", "FFmpeg is required for video conversion, but it was not found.")
            return
        if s["mode"] == MODE_SINGLE:
            input_file = Path(s["input_file"])
            if not input_file.is_file():
                self.post("error", "Choose a valid input video.")
                return
            temp_path = make_temp_output_path(s["output_format"])
            self.post("progress", 0, 1)
            self.post("status", "Converting video", input_file.name)
            convert_video(ffmpeg_path, input_file, temp_path, s["output_format"], s["quality"], s["resize"], s["gif_fps"], s["gif_width"], s["gif_custom_width"])
            self.post("progress", 1, 1)
            self.post("single_done", str(temp_path), f"{input_file.stem}.{s['output_format']}")
            return

        input_dir = Path(s["input_folder"])
        output_dir = Path(s["output_folder"])
        if not input_dir.is_dir():
            self.post("error", "Choose a valid input folder.")
            return
        if not s["output_folder"]:
            self.post("error", "Choose a valid output folder.")
            return
        output_dir.mkdir(parents=True, exist_ok=True)
        files = get_video_files(input_dir, s["include_subfolders"], output_dir)
        if not files:
            self.post("error", "No supported videos or GIFs found in that folder.")
            return
        self.post("progress", 0, len(files))
        self.post("log", f"Found {len(files)} media file(s)", "info")
        state = {"size": 0, "count": 0, "index": 1}
        success = 0
        for idx, file in enumerate(files, start=1):
            self.post("status", f"Converting {idx}/{len(files)}", file.name)
            out_path = None
            try:
                if s["batch"]["enabled"] and s["batch"]["method"] == BATCH_BY_COUNT:
                    target_dir = get_batch_folder(output_dir, idx, s["batch"]["batch_size"])
                elif s["batch"]["enabled"]:
                    target_dir = get_batch_folder_by_index(output_dir, state["index"])
                else:
                    target_dir = output_dir
                stem = file.stem if s["preserve_filename"] else str(idx)
                out_path = unique_output_path(target_dir, stem, s["output_format"])
                convert_video(ffmpeg_path, file, out_path, s["output_format"], s["quality"], s["resize"], s["gif_fps"], s["gif_width"], s["gif_custom_width"])
                if s["batch"]["enabled"] and s["batch"]["method"] == BATCH_BY_SIZE:
                    out_path = update_size_batch(out_path, state, output_dir, s["batch"]["max_bytes"])
                self.post("log", f"OK   {file.name} -> {out_path.name}", "ok")
                success += 1
            except Exception as exc:
                if out_path and out_path.exists():
                    out_path.unlink()
                self.post("log", f"FAIL {file.name}: {exc}", "err")
            self.post("progress", idx, len(files))
        self.post("done", f"Converted {success} of {len(files)} media file(s).", "Video conversion complete. Check the output folder.")


class VideoResizerPage(ToolPage):
    def __init__(self, theme_provider):
        super().__init__("Video Resizer", "Resize and compress videos with preset, custom, percentage, or target-size options.", theme_provider)
        self.mode = SegmentedControl([(MODE_BATCH, "Batch"), (MODE_SINGLE, "Single File")], MODE_BATCH)
        self.mode.on_changed(self._sync_mode)
        self.content_layout.addWidget(self.mode)
        self.engine = make_label("Video engine ready" if find_ffmpeg() else "Video engine unavailable", role="eyebrow")
        self.content_layout.addWidget(self.engine)

        self.batch_input = Card("Input and output")
        self.input_folder = PathPicker("Input folder", "Folder containing source videos.")
        self.output_folder = PathPicker("Output folder", "Folder for resized videos.")
        self.include_subfolders = QCheckBox("Include subfolders")
        self.batch_input.body_layout.addWidget(self.input_folder)
        self.batch_input.body_layout.addWidget(self.output_folder)
        self.batch_input.body_layout.addWidget(self.include_subfolders)
        self.content_layout.addWidget(self.batch_input)

        self.single_input = Card("Single file")
        self.input_file = PathPicker("Input video", "One source video file.", drop_kind="file", supported_extensions=SUPPORTED_VIDEO_INPUTS)
        self.single_input.body_layout.addWidget(self.input_file)
        self.content_layout.addWidget(self.single_input)

        self.settings = Card("Resize and compression")
        holder = QWidget()
        grid = make_grid(holder)
        self.resize_mode = combo(VIDEO_RESIZE_MODES, VIDEO_RESIZE_PRESET)
        self.preset = combo(PRESET_RESOLUTIONS, PRESET_1080)
        self.width = line("1920", integer=True)
        self.height = line("1080", integer=True)
        self.percentage = line("50", decimal=True)
        self.target_enabled = QCheckBox("Target max file size")
        self.target_mb = line("25", decimal=True)
        row = 0
        for label, widget in (
            (RESIZE_MODE, self.resize_mode),
            (PRESET, self.preset),
            (WIDTH, self.width),
            (HEIGHT, self.height),
            (PERCENTAGE, self.percentage),
            (TARGET_SIZE, self.target_enabled),
            (TARGET_MB, self.target_mb),
        ):
            row = add_grid_row(grid, row, label, widget)
        self.settings.body_layout.addWidget(holder)
        self.preserve_filename = QCheckBox("Preserve source file names")
        self.preserve_filename.setChecked(True)
        self.settings.body_layout.addWidget(self.preserve_filename)
        self.content_layout.addWidget(self.settings)

        self.batch_options = BatchOptions(count_label="Videos per folder", count_default="20", size_default="1000")
        self.content_layout.addWidget(self.batch_options)
        self.content_layout.addStretch(1)

        self.input_folder.button.clicked.connect(self._choose_input_folder)
        self.output_folder.button.clicked.connect(self._choose_output_folder)
        self.input_file.button.clicked.connect(self._choose_input_file)
        self.resize_mode.currentTextChanged.connect(lambda _text: self._sync_resize_fields())
        self.target_enabled.toggled.connect(lambda _checked: self._sync_resize_fields())
        self.add_action("Resize Videos", self._start)
        self._sync_mode(MODE_BATCH)
        self._sync_resize_fields()

    def _sync_mode(self, mode: str):
        single = mode == MODE_SINGLE
        self.batch_input.setVisible(not single)
        self.batch_options.setVisible(not single)
        self.preserve_filename.setVisible(not single)
        self.single_input.setVisible(single)
        if self.action_button:
            self.action_button.setText("Resize Video" if single else "Resize Videos")

    def _sync_resize_fields(self):
        mode = self.resize_mode.currentText()
        self.preset.setEnabled(mode == VIDEO_RESIZE_PRESET)
        self.width.setEnabled(mode == VIDEO_RESIZE_CUSTOM)
        self.height.setEnabled(mode == VIDEO_RESIZE_CUSTOM)
        self.percentage.setEnabled(mode == VIDEO_RESIZE_PERCENT)
        self.target_mb.setEnabled(self.target_enabled.isChecked())

    def _choose_input_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose input folder")
        if folder:
            self.input_folder.set_path(folder)
            if not self.output_folder.path():
                path = Path(folder)
                self.output_folder.set_path(path.parent / f"{path.name}_video_resized")

    def _choose_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if folder:
            self.output_folder.set_path(folder)

    def _choose_input_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose input video", "", f"{file_filter('Videos', SUPPORTED_VIDEO_INPUTS)};;All files (*.*)")
        if path:
            self.input_file.set_path(path)

    def _snapshot(self) -> dict:
        mode = self.resize_mode.currentText()
        return {
            "mode": self.mode.value(),
            "input_folder": self.input_folder.path(),
            "output_folder": self.output_folder.path(),
            "input_file": self.input_file.path(),
            "include_subfolders": self.include_subfolders.isChecked(),
            "resize_mode": mode,
            "preset": self.preset.currentText(),
            "width": parse_video_positive_int(self.width.text(), WIDTH) if mode == VIDEO_RESIZE_CUSTOM else None,
            "height": parse_video_positive_int(self.height.text(), HEIGHT) if mode == VIDEO_RESIZE_CUSTOM else None,
            "percentage": parse_video_percentage(self.percentage.text()) if mode == VIDEO_RESIZE_PERCENT else None,
            "quality": VIDEO_RESIZE_QUALITY_BALANCED,
            "target_bytes": parse_optional_target_bytes(self.target_mb.text()) if self.target_enabled.isChecked() else None,
            "preserve_filename": self.preserve_filename.isChecked(),
            "batch": self.batch_options.snapshot(),
        }

    def _start(self):
        try:
            self.start_worker(self._snapshot())
        except ValueError as exc:
            show_message(self, "Error", str(exc), self.theme(), "error")

    def run_task(self, s: dict):
        ffmpeg_path = find_ffmpeg()
        if not ffmpeg_path:
            self.post("error", "FFmpeg is required for video resizing, but it was not found.")
            return
        if s["mode"] == MODE_SINGLE:
            input_file = Path(s["input_file"])
            if not input_file.is_file():
                self.post("error", "Choose a valid input video.")
                return
            output_format = original_video_output_format(input_file)
            temp_path = make_temp_output_path(output_format)
            self.post("progress", 0, 1)
            resize_video(ffmpeg_path, input_file, temp_path, output_format, s["resize_mode"], s["preset"], s["width"], s["height"], s["percentage"], s["quality"], s["target_bytes"])
            self.post("progress", 1, 1)
            self.post("single_done", str(temp_path), f"{input_file.stem}.{output_format}")
            return

        input_dir = Path(s["input_folder"])
        output_dir = Path(s["output_folder"])
        if not input_dir.is_dir():
            self.post("error", "Choose a valid input folder.")
            return
        if not s["output_folder"]:
            self.post("error", "Choose a valid output folder.")
            return
        output_dir.mkdir(parents=True, exist_ok=True)
        files = get_video_files(input_dir, s["include_subfolders"], output_dir)
        if not files:
            self.post("error", "No supported videos or GIFs found in that folder.")
            return
        self.post("progress", 0, len(files))
        self.post("log", f"Found {len(files)} video file(s)", "info")
        state = {"size": 0, "count": 0, "index": 1}
        success = 0
        for idx, file in enumerate(files, start=1):
            self.post("status", f"Resizing {idx}/{len(files)}", file.name)
            out_path = None
            try:
                if s["batch"]["enabled"] and s["batch"]["method"] == BATCH_BY_COUNT:
                    target_dir = get_batch_folder(output_dir, idx, s["batch"]["batch_size"])
                elif s["batch"]["enabled"]:
                    target_dir = get_batch_folder_by_index(output_dir, state["index"])
                else:
                    target_dir = output_dir
                stem = file.stem if s["preserve_filename"] else str(idx)
                output_format = original_video_output_format(file)
                out_path = unique_output_path(target_dir, stem, output_format)
                resize_video(ffmpeg_path, file, out_path, output_format, s["resize_mode"], s["preset"], s["width"], s["height"], s["percentage"], s["quality"], s["target_bytes"])
                if s["batch"]["enabled"] and s["batch"]["method"] == BATCH_BY_SIZE:
                    out_path = update_size_batch(out_path, state, output_dir, s["batch"]["max_bytes"])
                self.post("log", f"OK   {file.name} -> {out_path.name}", "ok")
                success += 1
            except Exception as exc:
                if out_path and out_path.exists():
                    out_path.unlink()
                self.post("log", f"FAIL {file.name}: {exc}", "err")
            self.post("progress", idx, len(files))
        self.post("done", f"Processed {success} of {len(files)} video file(s).", "Video resize complete. Check the output folder.")


class AudioConverterPage(ToolPage):
    def __init__(self, theme_provider):
        super().__init__("Audio Converter", "Convert audio files or extract audio from video files.", theme_provider)
        self.mode = SegmentedControl([(MODE_BATCH, "Batch"), (MODE_SINGLE, "Single File")], MODE_BATCH)
        self.mode.on_changed(self._sync_mode)
        self.content_layout.addWidget(self.mode)
        self.engine = make_label("Audio engine ready" if find_ffmpeg() else "Audio engine unavailable", role="eyebrow")
        self.content_layout.addWidget(self.engine)

        self.batch_input = Card("Input and output")
        self.input_folder = PathPicker("Input folder", "Folder containing audio or video files.")
        self.output_folder = PathPicker("Output folder", "Folder for converted audio.")
        self.include_subfolders = QCheckBox("Include subfolders")
        self.batch_input.body_layout.addWidget(self.input_folder)
        self.batch_input.body_layout.addWidget(self.output_folder)
        self.batch_input.body_layout.addWidget(self.include_subfolders)
        self.content_layout.addWidget(self.batch_input)

        self.single_input = Card("Single file")
        self.input_file = PathPicker("Input audio or video", "One source audio or video file.", drop_kind="file", supported_extensions=SUPPORTED_AUDIO_INPUTS)
        self.single_input.body_layout.addWidget(self.input_file)
        self.content_layout.addWidget(self.single_input)

        self.settings = Card("Settings")
        holder = QWidget()
        grid = make_grid(holder)
        self.input_filter = combo(INPUT_TYPE_FILTERS, FILTER_AUDIO_ONLY)
        self.output_format = combo(OUTPUT_AUDIO_FORMATS, "mp3")
        self.quality = combo(AUDIO_QUALITY_PRESETS, AUDIO_QUALITY_BALANCED)
        row = 0
        row = add_grid_row(grid, row, INPUT_FILTER, self.input_filter)
        row = add_grid_row(grid, row, OUTPUT_FORMAT, self.output_format)
        add_grid_row(grid, row, QUALITY, self.quality)
        self.settings.body_layout.addWidget(holder)
        self.preserve_filename = QCheckBox("Preserve source file names")
        self.preserve_filename.setChecked(True)
        self.settings.body_layout.addWidget(self.preserve_filename)
        self.content_layout.addWidget(self.settings)

        self.batch_options = BatchOptions(count_label="Audio files per folder", count_default="40", size_default="500")
        self.content_layout.addWidget(self.batch_options)
        self.content_layout.addStretch(1)

        self.input_folder.button.clicked.connect(self._choose_input_folder)
        self.output_folder.button.clicked.connect(self._choose_output_folder)
        self.input_file.button.clicked.connect(self._choose_input_file)
        self.add_action("Convert Audio", self._start)
        self._sync_mode(MODE_BATCH)

    def _sync_mode(self, mode: str):
        single = mode == MODE_SINGLE
        self.batch_input.setVisible(not single)
        self.batch_options.setVisible(not single)
        self.preserve_filename.setVisible(not single)
        self.single_input.setVisible(single)

    def _choose_input_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose input folder")
        if folder:
            self.input_folder.set_path(folder)
            if not self.output_folder.path():
                path = Path(folder)
                self.output_folder.set_path(path.parent / f"{path.name}_audio_output")

    def _choose_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if folder:
            self.output_folder.set_path(folder)

    def _choose_input_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose input audio or video", "", f"{file_filter('Audio and video', SUPPORTED_AUDIO_INPUTS)};;All files (*.*)")
        if path:
            self.input_file.set_path(path)

    def _snapshot(self) -> dict:
        return {
            "mode": self.mode.value(),
            "input_folder": self.input_folder.path(),
            "output_folder": self.output_folder.path(),
            "input_file": self.input_file.path(),
            "include_subfolders": self.include_subfolders.isChecked(),
            "input_filter": self.input_filter.currentText(),
            "output_format": self.output_format.currentText().lower(),
            "quality": self.quality.currentText(),
            "preserve_filename": self.preserve_filename.isChecked(),
            "batch": self.batch_options.snapshot(),
        }

    def _start(self):
        try:
            self.start_worker(self._snapshot())
        except ValueError as exc:
            show_message(self, "Error", str(exc), self.theme(), "error")

    def run_task(self, s: dict):
        ffmpeg_path = find_ffmpeg()
        if not ffmpeg_path:
            self.post("error", "FFmpeg is required for audio conversion, but it was not found.")
            return
        if s["mode"] == MODE_SINGLE:
            input_file = Path(s["input_file"])
            if not input_file.is_file():
                self.post("error", "Choose a valid input audio or video file.")
                return
            temp_path = make_temp_output_path(s["output_format"])
            self.post("progress", 0, 1)
            convert_audio(ffmpeg_path, input_file, temp_path, s["output_format"], s["quality"])
            self.post("progress", 1, 1)
            self.post("single_done", str(temp_path), f"{input_file.stem}.{s['output_format']}")
            return

        input_dir = Path(s["input_folder"])
        output_dir = Path(s["output_folder"])
        if not input_dir.is_dir():
            self.post("error", "Choose a valid input folder.")
            return
        if not s["output_folder"]:
            self.post("error", "Choose a valid output folder.")
            return
        output_dir.mkdir(parents=True, exist_ok=True)
        files = get_audio_inputs(input_dir, s["include_subfolders"], s["input_filter"], output_dir)
        if not files:
            self.post("error", "No supported audio inputs found in that folder.")
            return
        self.post("progress", 0, len(files))
        self.post("log", f"Found {len(files)} input file(s)", "info")
        self.post("log", f"Quality : {describe_audio_quality(s['output_format'], s['quality'])}", "dim")
        state = {"size": 0, "count": 0, "index": 1}
        success = 0
        for idx, file in enumerate(files, start=1):
            self.post("status", f"Converting {idx}/{len(files)}", file.name)
            out_path = None
            try:
                if s["batch"]["enabled"] and s["batch"]["method"] == BATCH_BY_COUNT:
                    target_dir = get_batch_folder(output_dir, idx, s["batch"]["batch_size"])
                elif s["batch"]["enabled"]:
                    target_dir = get_batch_folder_by_index(output_dir, state["index"])
                else:
                    target_dir = output_dir
                stem = file.stem if s["preserve_filename"] else str(idx)
                out_path = unique_output_path(target_dir, stem, s["output_format"])
                convert_audio(ffmpeg_path, file, out_path, s["output_format"], s["quality"])
                if s["batch"]["enabled"] and s["batch"]["method"] == BATCH_BY_SIZE:
                    out_path = update_size_batch(out_path, state, output_dir, s["batch"]["max_bytes"])
                self.post("log", f"OK   {file.name} -> {out_path.name}", "ok")
                success += 1
            except Exception as exc:
                if out_path and out_path.exists():
                    out_path.unlink()
                self.post("log", f"FAIL {file.name}: {exc}", "err")
            self.post("progress", idx, len(files))
        self.post("done", f"Converted {success} of {len(files)} audio input(s).", "Audio conversion complete. Check the output folder.")


class MixedMediaPage(ToolPage):
    def __init__(self, theme_provider):
        super().__init__("Mixed Media Converter", "Convert image, video, GIF, and audio formats together while keeping output organized.", theme_provider)
        self.engine = make_label("Media engine ready" if find_ffmpeg() else "Media engine ready for images", role="eyebrow")
        self.content_layout.addWidget(self.engine)

        self.io = Card("Input and output")
        self.input_folder = PathPicker("Input folder", "Folder containing mixed media.")
        self.output_folder = PathPicker("Output folder", "Folder for converted media.")
        self.include_subfolders = QCheckBox("Include subfolders")
        self.io.body_layout.addWidget(self.input_folder)
        self.io.body_layout.addWidget(self.output_folder)
        self.io.body_layout.addWidget(self.include_subfolders)
        self.content_layout.addWidget(self.io)

        self.media = Card("Media types")
        self.convert_images = QCheckBox("Images")
        self.convert_videos = QCheckBox("Videos / GIFs")
        self.convert_audio = QCheckBox("Audio")
        for check in (self.convert_images, self.convert_videos, self.convert_audio):
            check.setChecked(True)
            self.media.body_layout.addWidget(check)
        self.content_layout.addWidget(self.media)

        self.image_settings = Card("Image Conversion")
        holder = QWidget()
        grid = make_grid(holder)
        self.image_format = combo(get_output_formats(), "jpg")
        add_grid_row(grid, 0, OUTPUT_FORMAT, self.image_format)
        self.image_settings.body_layout.addWidget(holder)
        self.content_layout.addWidget(self.image_settings)

        self.video_settings = Card("Video Converter")
        holder = QWidget()
        grid = make_grid(holder)
        self.video_format = combo(OUTPUT_VIDEO_FORMATS, "mp4")
        self.gif_fps = combo(GIF_FPS_OPTIONS, GIF_FPS_ORIGINAL)
        self.gif_width = combo(GIF_WIDTH_OPTIONS, GIF_WIDTH_KEEP)
        self.gif_custom_width = line("", integer=True)
        row = 0
        row = add_grid_row(grid, row, OUTPUT_FORMAT, self.video_format)
        gif_fps_row = row
        row = add_grid_row(grid, row, GIF_FPS, self.gif_fps)
        gif_width_row = row
        row = add_grid_row(grid, row, GIF_WIDTH, self.gif_width)
        gif_custom_width_row = row
        add_grid_row(grid, row, CUSTOM_GIF_WIDTH, self.gif_custom_width)
        self.gif_rows = [
            grid_row_widgets(grid, gif_fps_row),
            grid_row_widgets(grid, gif_width_row),
        ]
        self.gif_custom_width_row = grid_row_widgets(grid, gif_custom_width_row)
        self.video_settings.body_layout.addWidget(holder)
        self.content_layout.addWidget(self.video_settings)

        self.audio_settings = Card("Audio Converter")
        holder = QWidget()
        grid = make_grid(holder)
        self.audio_input_filter = combo(INPUT_TYPE_FILTERS, FILTER_AUDIO_ONLY)
        self.audio_format = combo(OUTPUT_AUDIO_FORMATS, "mp3")
        self.audio_quality = combo(AUDIO_QUALITY_PRESETS, AUDIO_QUALITY_BALANCED)
        row = 0
        row = add_grid_row(grid, row, INPUT_FILTER, self.audio_input_filter)
        row = add_grid_row(grid, row, OUTPUT_FORMAT, self.audio_format)
        add_grid_row(grid, row, QUALITY, self.audio_quality)
        self.audio_settings.body_layout.addWidget(holder)
        self.content_layout.addWidget(self.audio_settings)

        self.output_settings = Card("Output")
        holder = QWidget()
        grid = make_grid(holder)
        self.organization = combo(OUTPUT_ORGANIZATION_OPTIONS, ORG_ONE_FOLDER)
        add_grid_row(grid, 0, "Output layout", self.organization)
        self.output_settings.body_layout.addWidget(holder)
        self.preserve_filename = QCheckBox("Preserve source file names")
        self.preserve_filename.setChecked(True)
        self.output_settings.body_layout.addWidget(self.preserve_filename)
        self.content_layout.addWidget(self.output_settings)

        self.batch_options = BatchOptions(count_label="Files per folder", count_default="40", size_default="1000")
        self.content_layout.addWidget(self.batch_options)
        self.content_layout.addStretch(1)
        self.input_folder.button.clicked.connect(self._choose_input_folder)
        self.output_folder.button.clicked.connect(self._choose_output_folder)
        self.video_format.currentTextChanged.connect(lambda _text: self._sync_video_format())
        self.gif_width.currentTextChanged.connect(lambda _text: self._sync_video_format())
        self.convert_images.toggled.connect(lambda _checked: self._sync_media_sections())
        self.convert_videos.toggled.connect(lambda _checked: self._sync_media_sections())
        self.convert_audio.toggled.connect(lambda _checked: self._sync_media_sections())
        self.add_action("Convert Mixed Media", self._start)
        self._sync_media_sections()

    def _choose_input_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose input folder")
        if folder:
            self.input_folder.set_path(folder)
            if not self.output_folder.path():
                path = Path(folder)
                self.output_folder.set_path(path.parent / f"{path.name}_mixed_output")

    def _choose_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if folder:
            self.output_folder.set_path(folder)

    def _enabled_media(self) -> set[str]:
        enabled = set()
        if self.convert_images.isChecked():
            enabled.add(MEDIA_IMAGE)
        if self.convert_videos.isChecked():
            enabled.add(MEDIA_VIDEO)
        if self.convert_audio.isChecked():
            enabled.add(MIXED_AUDIO)
        return enabled

    def _sync_video_format(self):
        gif = self.video_format.currentText().lower() == "gif"
        custom_width = gif and self.gif_width.currentText() == GIF_WIDTH_CUSTOM
        for row in self.gif_rows:
            for widget in row:
                widget.setVisible(gif)
                widget.setEnabled(gif)
        for widget in self.gif_custom_width_row:
            widget.setVisible(custom_width)
            widget.setEnabled(custom_width)

    def _sync_media_sections(self):
        self.image_settings.setVisible(self.convert_images.isChecked())
        self.video_settings.setVisible(self.convert_videos.isChecked())
        self.audio_settings.setVisible(self.convert_audio.isChecked())
        self._sync_video_format()

    def _gif_custom(self) -> int | None:
        if self.video_format.currentText().lower() != "gif" or self.gif_width.currentText() != GIF_WIDTH_CUSTOM:
            return None
        value = self.gif_custom_width.text().strip()
        if not value:
            raise ValueError("Custom GIF width is required.")
        parsed = int(value)
        if parsed <= 0:
            raise ValueError("Custom GIF width must be greater than zero.")
        return parsed

    def _start(self):
        try:
            snapshot = {
                "input_folder": self.input_folder.path(),
                "output_folder": self.output_folder.path(),
                "include_subfolders": self.include_subfolders.isChecked(),
                "enabled_media": self._enabled_media(),
                "image_format": self.image_format.currentText().lower(),
                "video_format": self.video_format.currentText().lower(),
                "video_quality": VIDEO_QUALITY_BALANCED,
                "gif_fps": self.gif_fps.currentText(),
                "gif_width": self.gif_width.currentText(),
                "gif_custom_width": self._gif_custom() if self.convert_videos.isChecked() else None,
                "audio_input_filter": self.audio_input_filter.currentText(),
                "audio_format": self.audio_format.currentText().lower(),
                "audio_quality": self.audio_quality.currentText(),
                "organization": self.organization.currentText(),
                "preserve_filename": self.preserve_filename.isChecked(),
                "batch": self.batch_options.snapshot(),
            }
        except ValueError as exc:
            show_message(self, "Error", str(exc), self.theme(), "error")
            return
        self.start_worker(snapshot)

    def _base_output_dir(self, output_dir: Path, media_type: str, organization: str) -> Path:
        if organization == ORG_MEDIA_FOLDERS:
            return output_dir / MEDIA_FOLDER_NAMES[media_type]
        return output_dir

    def run_task(self, s: dict):
        input_dir = Path(s["input_folder"])
        output_dir = Path(s["output_folder"])
        if not input_dir.is_dir():
            self.post("error", "Choose a valid input folder.")
            return
        if not s["output_folder"]:
            self.post("error", "Choose a valid output folder.")
            return
        enabled = set(s["enabled_media"])
        ffmpeg_path = find_ffmpeg()
        if not ffmpeg_path:
            enabled = {media for media in enabled if media == MEDIA_IMAGE}
        if not enabled:
            self.post("error", "Media conversion unavailable. Required components are missing.")
            return
        output_dir.mkdir(parents=True, exist_ok=True)
        files = collect_media_files(input_dir, s["include_subfolders"], enabled, output_dir, s["audio_input_filter"])
        if not files:
            self.post("error", "No supported media files found in that folder.")
            return
        self.post("progress", 0, len(files))
        self.post("log", f"Found {len(files)} media file(s)", "info")
        media_counts = {MEDIA_IMAGE: 0, MEDIA_VIDEO: 0, MIXED_AUDIO: 0}
        states = {}
        success = 0
        for idx, (file, media_type) in enumerate(files, start=1):
            media_counts[media_type] += 1
            media_index = media_counts[media_type]
            self.post("status", f"Converting {idx}/{len(files)}", file.name)
            out_path = None
            try:
                base_dir = self._base_output_dir(output_dir, media_type, s["organization"])
                key = str(base_dir)
                states.setdefault(key, {"size": 0, "count": 0, "index": 1})
                state = states[key]
                if s["batch"]["enabled"] and s["batch"]["method"] == BATCH_BY_COUNT:
                    item_number = media_index if s["organization"] == ORG_MEDIA_FOLDERS else idx
                    target_dir = get_batch_folder(base_dir, item_number, s["batch"]["batch_size"])
                elif s["batch"]["enabled"]:
                    target_dir = get_batch_folder_by_index(base_dir, state["index"])
                else:
                    target_dir = base_dir
                extension = media_output_extension(media_type, s["image_format"], s["video_format"], s["audio_format"])
                stem = file.stem if s["preserve_filename"] else f"{media_type}_{media_index:03d}"
                out_path = unique_output_path(target_dir, stem, extension)
                convert_mixed_file(
                    source_file=file,
                    media_type=media_type,
                    output_file=out_path,
                    image_format=s["image_format"],
                    ffmpeg_path=ffmpeg_path,
                    video_format=s["video_format"],
                    audio_format=s["audio_format"],
                    audio_quality=s["audio_quality"],
                    video_quality=s["video_quality"],
                    gif_fps=s["gif_fps"],
                    gif_width_option=s["gif_width"],
                    gif_custom_width=s["gif_custom_width"],
                )
                if s["batch"]["enabled"] and s["batch"]["method"] == BATCH_BY_SIZE:
                    out_path = update_size_batch(out_path, state, base_dir, s["batch"]["max_bytes"])
                self.post("log", f"OK   {MEDIA_LABELS[media_type]}: {file.name} -> {out_path.name}", "ok")
                success += 1
            except Exception as exc:
                if out_path and out_path.exists():
                    out_path.unlink()
                self.post("log", f"FAIL {file.name}: {exc}", "err")
            self.post("progress", idx, len(files))
        self.post("done", f"Converted {success} of {len(files)} media file(s).", "Mixed media conversion complete. Check the output folder.")


class MixedMediaResizerPage(ToolPage):
    def __init__(self, theme_provider):
        super().__init__("Mixed Media Resizer", "Resize and compress mixed image, video, and GIF folders while preserving source formats.", theme_provider)
        self.engine = make_label("Media engine ready" if find_ffmpeg() else "Media engine ready for images", role="eyebrow")
        self.content_layout.addWidget(self.engine)

        self.io = Card("Input and output")
        self.input_folder = PathPicker("Input folder", "Folder containing mixed images and videos.")
        self.output_folder = PathPicker("Output folder", "Folder for resized media.")
        self.include_subfolders = QCheckBox("Include subfolders")
        self.io.body_layout.addWidget(self.input_folder)
        self.io.body_layout.addWidget(self.output_folder)
        self.io.body_layout.addWidget(self.include_subfolders)
        self.content_layout.addWidget(self.io)

        self.media = Card("Media types")
        self.resize_images = QCheckBox("Images")
        self.resize_videos = QCheckBox("Videos / GIFs")
        for check in (self.resize_images, self.resize_videos):
            check.setChecked(True)
            self.media.body_layout.addWidget(check)
        self.content_layout.addWidget(self.media)

        self.image_settings = Card("Image Resizer")
        holder = QWidget()
        grid = make_grid(holder)
        self.image_resize_mode = combo(IMAGE_RESIZE_MODES, RESIZE_BY_WIDTH)
        self.image_width = line("1920", integer=True)
        self.image_height = line("1080", integer=True)
        self.image_percentage = line("50", decimal=True)
        self.image_max_size_enabled = QCheckBox("Target max file size")
        self.image_max_mb = line("2", decimal=True)
        row = 0
        row = add_grid_row(grid, row, RESIZE_MODE, self.image_resize_mode)
        row = add_grid_row(grid, row, WIDTH, self.image_width)
        row = add_grid_row(grid, row, HEIGHT, self.image_height)
        row = add_grid_row(grid, row, PERCENTAGE, self.image_percentage)
        row = add_grid_row(grid, row, SIZE_LIMIT, self.image_max_size_enabled)
        add_grid_row(grid, row, MAX_MB, self.image_max_mb)
        self.image_settings.body_layout.addWidget(holder)
        self.content_layout.addWidget(self.image_settings)

        self.video_settings = Card("Video Resizer")
        holder = QWidget()
        grid = make_grid(holder)
        self.video_resize_mode = combo(VIDEO_RESIZE_MODES, VIDEO_RESIZE_PRESET)
        self.video_preset = combo(PRESET_RESOLUTIONS, PRESET_1080)
        self.video_width = line("1920", integer=True)
        self.video_height = line("1080", integer=True)
        self.video_percentage = line("50", decimal=True)
        self.video_target_enabled = QCheckBox("Target max file size")
        self.video_target_mb = line("25", decimal=True)
        row = 0
        row = add_grid_row(grid, row, RESIZE_MODE, self.video_resize_mode)
        row = add_grid_row(grid, row, PRESET, self.video_preset)
        row = add_grid_row(grid, row, WIDTH, self.video_width)
        row = add_grid_row(grid, row, HEIGHT, self.video_height)
        row = add_grid_row(grid, row, PERCENTAGE, self.video_percentage)
        row = add_grid_row(grid, row, TARGET_SIZE, self.video_target_enabled)
        add_grid_row(grid, row, TARGET_MB, self.video_target_mb)
        self.video_settings.body_layout.addWidget(holder)
        self.content_layout.addWidget(self.video_settings)

        self.output_settings = Card("Output")
        holder = QWidget()
        grid = make_grid(holder)
        self.organization = combo(OUTPUT_ORGANIZATION_OPTIONS, ORG_ONE_FOLDER)
        add_grid_row(grid, 0, "Output layout", self.organization)
        self.output_settings.body_layout.addWidget(holder)
        self.preserve_filename = QCheckBox("Preserve source file names")
        self.preserve_filename.setChecked(True)
        self.output_settings.body_layout.addWidget(self.preserve_filename)
        self.content_layout.addWidget(self.output_settings)

        self.batch_options = BatchOptions(count_label="Files per folder", count_default="40", size_default="1000")
        self.content_layout.addWidget(self.batch_options)
        self.content_layout.addStretch(1)

        self.input_folder.button.clicked.connect(self._choose_input_folder)
        self.output_folder.button.clicked.connect(self._choose_output_folder)
        self.resize_images.toggled.connect(lambda _checked: self._sync_media_sections())
        self.resize_videos.toggled.connect(lambda _checked: self._sync_media_sections())
        self.image_resize_mode.currentTextChanged.connect(lambda _text: self._sync_resize_fields())
        self.image_max_size_enabled.toggled.connect(lambda _checked: self._sync_resize_fields())
        self.video_resize_mode.currentTextChanged.connect(lambda _text: self._sync_resize_fields())
        self.video_target_enabled.toggled.connect(lambda _checked: self._sync_resize_fields())
        self.add_action("Resize Mixed Media", self._start)
        self._sync_media_sections()

    def _choose_input_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose input folder")
        if folder:
            self.input_folder.set_path(folder)
            if not self.output_folder.path():
                path = Path(folder)
                self.output_folder.set_path(path.parent / f"{path.name}_mixed_resized")

    def _choose_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if folder:
            self.output_folder.set_path(folder)

    def _enabled_media(self) -> set[str]:
        enabled = set()
        if self.resize_images.isChecked():
            enabled.add(MEDIA_IMAGE)
        if self.resize_videos.isChecked():
            enabled.add(MEDIA_VIDEO)
        return enabled

    def _sync_resize_fields(self):
        image_mode = self.image_resize_mode.currentText()
        self.image_width.setEnabled(image_mode in {RESIZE_BY_WIDTH, RESIZE_EXACT})
        self.image_height.setEnabled(image_mode in {RESIZE_BY_HEIGHT, RESIZE_EXACT})
        self.image_percentage.setEnabled(image_mode == IMAGE_RESIZE_PERCENT)
        self.image_max_mb.setEnabled(self.image_max_size_enabled.isChecked())

        video_mode = self.video_resize_mode.currentText()
        self.video_preset.setEnabled(video_mode == VIDEO_RESIZE_PRESET)
        self.video_width.setEnabled(video_mode == VIDEO_RESIZE_CUSTOM)
        self.video_height.setEnabled(video_mode == VIDEO_RESIZE_CUSTOM)
        self.video_percentage.setEnabled(video_mode == VIDEO_RESIZE_PERCENT)
        self.video_target_mb.setEnabled(self.video_target_enabled.isChecked())

    def _sync_media_sections(self):
        self.image_settings.setVisible(self.resize_images.isChecked())
        self.video_settings.setVisible(self.resize_videos.isChecked())
        self._sync_resize_fields()

    def _start(self):
        try:
            image_mode = self.image_resize_mode.currentText()
            video_mode = self.video_resize_mode.currentText()
            image_enabled = self.resize_images.isChecked()
            video_enabled = self.resize_videos.isChecked()
            snapshot = {
                "input_folder": self.input_folder.path(),
                "output_folder": self.output_folder.path(),
                "include_subfolders": self.include_subfolders.isChecked(),
                "enabled_media": self._enabled_media(),
                "image_resize_mode": image_mode,
                "image_width": parse_image_positive_int(self.image_width.text(), WIDTH) if image_enabled and image_mode in {RESIZE_BY_WIDTH, RESIZE_EXACT} else None,
                "image_height": parse_image_positive_int(self.image_height.text(), HEIGHT) if image_enabled and image_mode in {RESIZE_BY_HEIGHT, RESIZE_EXACT} else None,
                "image_percentage": parse_image_percentage(self.image_percentage.text()) if image_enabled and image_mode == IMAGE_RESIZE_PERCENT else None,
                "image_max_bytes": parse_optional_max_bytes(self.image_max_mb.text()) if image_enabled and self.image_max_size_enabled.isChecked() else None,
                "video_resize_mode": video_mode,
                "video_preset": self.video_preset.currentText(),
                "video_width": parse_video_positive_int(self.video_width.text(), WIDTH) if video_enabled and video_mode == VIDEO_RESIZE_CUSTOM else None,
                "video_height": parse_video_positive_int(self.video_height.text(), HEIGHT) if video_enabled and video_mode == VIDEO_RESIZE_CUSTOM else None,
                "video_percentage": parse_video_percentage(self.video_percentage.text()) if video_enabled and video_mode == VIDEO_RESIZE_PERCENT else None,
                "video_target_bytes": parse_optional_target_bytes(self.video_target_mb.text()) if video_enabled and self.video_target_enabled.isChecked() else None,
                "organization": self.organization.currentText(),
                "preserve_filename": self.preserve_filename.isChecked(),
                "batch": self.batch_options.snapshot(),
            }
        except ValueError as exc:
            show_message(self, "Error", str(exc), self.theme(), "error")
            return
        self.start_worker(snapshot)

    def _base_output_dir(self, output_dir: Path, media_type: str, organization: str) -> Path:
        if organization == ORG_MEDIA_FOLDERS:
            return output_dir / MEDIA_FOLDER_NAMES[media_type]
        return output_dir

    def run_task(self, s: dict):
        input_dir = Path(s["input_folder"])
        output_dir = Path(s["output_folder"])
        if not input_dir.is_dir():
            self.post("error", "Choose a valid input folder.")
            return
        if not s["output_folder"]:
            self.post("error", "Choose a valid output folder.")
            return
        enabled = set(s["enabled_media"])
        ffmpeg_path = find_ffmpeg()
        if not ffmpeg_path:
            enabled = {media for media in enabled if media == MEDIA_IMAGE}
        if not enabled:
            self.post("error", "Media resizing unavailable. Required components are missing.")
            return
        output_dir.mkdir(parents=True, exist_ok=True)
        files = collect_media_files(input_dir, s["include_subfolders"], enabled, output_dir)
        if not files:
            self.post("error", "No supported images, videos, or GIFs found in that folder.")
            return
        self.post("progress", 0, len(files))
        self.post("log", f"Found {len(files)} resizable media file(s)", "info")
        media_counts = {MEDIA_IMAGE: 0, MEDIA_VIDEO: 0}
        states = {}
        success = 0
        for idx, (file, media_type) in enumerate(files, start=1):
            media_counts[media_type] += 1
            media_index = media_counts[media_type]
            self.post("status", f"Resizing {idx}/{len(files)}", file.name)
            out_path = None
            try:
                base_dir = self._base_output_dir(output_dir, media_type, s["organization"])
                key = str(base_dir)
                states.setdefault(key, {"size": 0, "count": 0, "index": 1})
                state = states[key]
                if s["batch"]["enabled"] and s["batch"]["method"] == BATCH_BY_COUNT:
                    item_number = media_index if s["organization"] == ORG_MEDIA_FOLDERS else idx
                    target_dir = get_batch_folder(base_dir, item_number, s["batch"]["batch_size"])
                elif s["batch"]["enabled"]:
                    target_dir = get_batch_folder_by_index(base_dir, state["index"])
                else:
                    target_dir = base_dir
                extension = media_original_output_extension(media_type, file)
                stem = file.stem if s["preserve_filename"] else f"{media_type}_{media_index:03d}"
                out_path = unique_output_path(target_dir, stem, extension)
                resize_mixed_file(
                    source_file=file,
                    media_type=media_type,
                    output_file=out_path,
                    ffmpeg_path=ffmpeg_path,
                    image_resize_mode=s["image_resize_mode"],
                    image_width=s["image_width"],
                    image_height=s["image_height"],
                    image_percentage=s["image_percentage"],
                    image_quality=IMAGE_RESIZE_QUALITY_BALANCED,
                    image_max_bytes=s["image_max_bytes"],
                    video_resize_mode=s["video_resize_mode"],
                    video_preset_resolution=s["video_preset"],
                    video_width=s["video_width"],
                    video_height=s["video_height"],
                    video_percentage=s["video_percentage"],
                    video_quality=VIDEO_RESIZE_QUALITY_BALANCED,
                    video_target_bytes=s["video_target_bytes"],
                )
                if s["batch"]["enabled"] and s["batch"]["method"] == BATCH_BY_SIZE:
                    out_path = update_size_batch(out_path, state, base_dir, s["batch"]["max_bytes"])
                self.post("log", f"OK   {MEDIA_LABELS[media_type]}: {file.name} -> {out_path.name}", "ok")
                success += 1
            except Exception as exc:
                if out_path and out_path.exists():
                    out_path.unlink()
                self.post("log", f"FAIL {file.name}: {exc}", "err")
            self.post("progress", idx, len(files))
        self.post("done", f"Resized {success} of {len(files)} media file(s).", "Mixed media resize complete. Check the output folder.")


class FileSorterPage(ToolPage):
    def __init__(self, theme_provider):
        super().__init__("File Sorter", "Organize images, videos, and audio into clean folder structures.", theme_provider)
        self.io = Card("Input and output")
        self.input_folder = PathPicker("Input folder", "Folder containing files to sort.")
        self.output_folder = PathPicker("Output folder", "Folder where organized files will be copied or moved.")
        self.include_subfolders = QCheckBox("Include subfolders")
        self.io.body_layout.addWidget(self.input_folder)
        self.io.body_layout.addWidget(self.output_folder)
        self.io.body_layout.addWidget(self.include_subfolders)
        self.content_layout.addWidget(self.io)

        self.settings = Card("Sorting settings")
        self.sort_images = QCheckBox("Images")
        self.sort_videos = QCheckBox("Videos")
        self.sort_audio = QCheckBox("Audio")
        for check in (self.sort_images, self.sort_videos, self.sort_audio):
            check.setChecked(True)
        holder = QWidget()
        grid = make_grid(holder)
        self.operation = combo(OPERATION_MODES, MODE_COPY)
        self.structure = combo(FOLDER_STRUCTURES)
        row = 0
        row = add_grid_row(grid, row, "Mode", self.operation)
        row = add_grid_row(grid, row, FOLDER_STRUCTURE, self.structure)
        checks = QWidget()
        check_layout = QHBoxLayout(checks)
        check_layout.setContentsMargins(0, 0, 0, 0)
        check_layout.addWidget(self.sort_images)
        check_layout.addWidget(self.sort_videos)
        check_layout.addWidget(self.sort_audio)
        add_grid_row(grid, row, MEDIA_TYPES, checks)
        self.settings.body_layout.addWidget(holder)
        self.content_layout.addWidget(self.settings)

        self.preview = Card("Preview")
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMinimumHeight(150)
        self.preview.body_layout.addWidget(self.preview_text)
        preview_btn = make_button("Refresh Preview")
        preview_btn.clicked.connect(self._refresh_preview)
        self.preview.body_layout.addWidget(preview_btn)
        self.content_layout.addWidget(self.preview)
        self.content_layout.addStretch(1)

        self.input_folder.button.clicked.connect(self._choose_input_folder)
        self.output_folder.button.clicked.connect(self._choose_output_folder)
        self.add_action("Sort Files", self._start)

    def _choose_input_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose input folder")
        if folder:
            self.input_folder.set_path(folder)
            if not self.output_folder.path():
                path = Path(folder)
                self.output_folder.set_path(path.parent / f"{path.name}_sorted")

    def _choose_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if folder:
            self.output_folder.set_path(folder)

    def _enabled(self):
        enabled = set()
        if self.sort_images.isChecked():
            enabled.add(MEDIA_IMAGES)
        if self.sort_videos.isChecked():
            enabled.add(MEDIA_VIDEOS)
        if self.sort_audio.isChecked():
            enabled.add(MEDIA_AUDIO)
        return enabled

    def _preview_snapshot(self):
        return {
            "input_folder": self.input_folder.path(),
            "output_folder": self.output_folder.path(),
            "include_subfolders": self.include_subfolders.isChecked(),
            "enabled": self._enabled(),
            "structure": self.structure.currentText(),
            "operation": self.operation.currentText(),
        }

    def _refresh_preview(self):
        try:
            s = self._preview_snapshot()
            if not s["input_folder"] or not s["output_folder"] or not s["enabled"]:
                self.preview_text.setPlainText("Choose folders and at least one media type.")
                return
            preview = collect_sort_preview(Path(s["input_folder"]), Path(s["output_folder"]), s["include_subfolders"], s["enabled"], s["structure"])
            lines = [f"Ready: {len(preview.items)} file(s)", f"Skipped: {len(preview.unsupported) + len(preview.output_skipped)}", ""]
            for item in preview.items[:120]:
                lines.append(f"{item.source.name} -> {item.target_folder}")
            self.preview_text.setPlainText("\n".join(lines))
        except Exception as exc:
            self.preview_text.setPlainText(str(exc))

    def _start(self):
        if self.operation.currentText() == MODE_MOVE:
            if not ask_confirm(self, "Confirm move mode", "Move mode will remove files from the original folder. Continue?", self.theme()):
                return
        self.start_worker(self._preview_snapshot())

    def run_task(self, s: dict):
        if not s["enabled"]:
            self.post("error", "Choose at least one media type to sort.")
            return
        input_dir = Path(s["input_folder"])
        output_dir = Path(s["output_folder"])
        if not input_dir.is_dir():
            self.post("error", "Choose a valid input folder.")
            return
        if not s["output_folder"]:
            self.post("error", "Choose a valid output folder.")
            return
        output_dir.mkdir(parents=True, exist_ok=True)
        preview = collect_sort_preview(input_dir, output_dir, s["include_subfolders"], s["enabled"], s["structure"])
        total = len(preview.items)
        if total == 0:
            self.post("error", "No supported files found for the current settings.")
            return
        self.post("progress", 0, total)
        self.post("log", f"Found {total} file(s)", "info")
        for idx, item in enumerate(preview.items, start=1):
            self.post("status", f"Sorting {idx}/{total}", item.source.name)
            try:
                out_path = sort_file(item, s["operation"])
                self.post("log", f"OK   {item.source.name} -> {out_path}", "ok")
            except Exception as exc:
                self.post("log", f"FAIL {item.source.name}: {exc}", "err")
            self.post("progress", idx, total)
        self.post("done", f"Sorted {total} file(s).", "Sorting complete. Check the output folder.")


class BatchFoldersPage(ToolPage):
    def __init__(self, theme_provider):
        super().__init__("Batch Folders", "Copy files into numbered folders by file count or folder size.", theme_provider)
        self.io = Card("Input and output")
        self.input_folder = PathPicker("Input folder", "Folder containing files to batch.")
        self.output_folder = PathPicker("Output folder", "Folder where batch folders will be created.")
        self.include_subfolders = QCheckBox("Include subfolders")
        self.io.body_layout.addWidget(self.input_folder)
        self.io.body_layout.addWidget(self.output_folder)
        self.io.body_layout.addWidget(self.include_subfolders)
        self.content_layout.addWidget(self.io)

        self.settings = Card("Batch settings")
        holder = QWidget()
        grid = make_grid(holder)
        self.file_filter = combo(BATCH_FILE_FILTERS, BATCH_FILTER_IMAGES)
        self.method = combo(BATCH_METHODS, BATCH_BY_COUNT)
        self.batch_size = line("40", integer=True)
        self.max_mb = line("100", decimal=True)
        row = 0
        row = add_grid_row(grid, row, "File type", self.file_filter)
        row = add_grid_row(grid, row, "Batch method", self.method)
        row = add_grid_row(grid, row, "Files per folder", self.batch_size)
        add_grid_row(grid, row, MAX_FOLDER_SIZE, self.max_mb, "Size is measured from copied source files, in MB.")
        self.settings.body_layout.addWidget(holder)
        self.content_layout.addWidget(self.settings)
        self.content_layout.addStretch(1)
        self.method.currentTextChanged.connect(lambda _text: self._sync())
        self.input_folder.button.clicked.connect(self._choose_input_folder)
        self.output_folder.button.clicked.connect(self._choose_output_folder)
        self.add_action("Batch Folders", self._start)
        self._sync()

    def _sync(self):
        by_count = self.method.currentText() == BATCH_BY_COUNT
        self.batch_size.setEnabled(by_count)
        self.max_mb.setEnabled(not by_count)

    def _choose_input_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose input folder")
        if folder:
            self.input_folder.set_path(folder)
            if not self.output_folder.path():
                path = Path(folder)
                self.output_folder.set_path(path.parent / f"{path.name}_batches")

    def _choose_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if folder:
            self.output_folder.set_path(folder)

    def _start(self):
        try:
            method = self.method.currentText()
            snapshot = {
                "input_folder": self.input_folder.path(),
                "output_folder": self.output_folder.path(),
                "include_subfolders": self.include_subfolders.isChecked(),
                "file_filter": self.file_filter.currentText(),
                "method": method,
                "batch_size": parse_batch_size(self.batch_size.text()) if method == BATCH_BY_COUNT else None,
                "max_bytes": parse_folder_size_mb(self.max_mb.text()) if method == BATCH_BY_SIZE else None,
            }
        except ValueError:
            show_message(self, "Error", "Batch settings must be valid positive numbers.", self.theme(), "error")
            return
        self.start_worker(snapshot)

    def run_task(self, s: dict):
        input_dir = Path(s["input_folder"])
        output_dir = Path(s["output_folder"])
        if not input_dir.is_dir():
            self.post("error", "Choose a valid input folder.")
            return
        if not s["output_folder"]:
            self.post("error", "Choose a valid output folder.")
            return
        output_dir.mkdir(parents=True, exist_ok=True)
        files = self._collect_files(input_dir, s["include_subfolders"], s["file_filter"])
        files = remove_files_inside_output_folder(files, output_dir)
        if not files:
            self.post("error", "No files found for the selected file type.")
            return
        self.post("progress", 0, len(files))
        state = {"size": 0, "count": 0, "index": 1}
        for idx, file in enumerate(files, start=1):
            self.post("status", f"Batching {idx}/{len(files)}", file.name)
            if s["method"] == BATCH_BY_COUNT:
                batch_dir = get_batch_folder(output_dir, idx, s["batch_size"])
            else:
                next_size = file.stat().st_size
                if should_start_new_size_batch(state["size"], next_size, s["max_bytes"], state["count"]):
                    state["index"] += 1
                    state["size"] = 0
                    state["count"] = 0
                batch_dir = get_batch_folder_by_index(output_dir, state["index"])
                state["size"] += next_size
                state["count"] += 1
            out_path = copy_file_to_batch_folder(file, batch_dir)
            self.post("log", f"OK   {file.name} -> {out_path.parent.name}", "ok")
            self.post("progress", idx, len(files))
        self.post("done", f"Batched {len(files)} file(s).", "Batching complete. Check the output folder.")

    def _collect_files(self, input_dir: Path, include_subfolders: bool, file_filter_text: str) -> list[Path]:
        paths = input_dir.rglob("*") if include_subfolders else input_dir.iterdir()

        files = [
            path for path in paths
            if path.is_file() and self._matches_filter(path, file_filter_text)
        ]

        from app.core.file_utils import natural_sort_key
        return sorted(files, key=natural_sort_key)

    def _matches_filter(self, path: Path, file_filter_text: str) -> bool:
        suffix = path.suffix.lower()

        if file_filter_text == BATCH_FILTER_IMAGES:
            return suffix in SUPPORTED_INPUTS

        if file_filter_text == BATCH_FILTER_VIDEOS:
            return suffix in SUPPORTED_VIDEO_INPUTS

        if file_filter_text == BATCH_FILTER_AUDIO:
            return suffix in AUDIO_INPUT_EXTENSIONS

        if file_filter_text == BATCH_FILTER_SUPPORTED_MEDIA:
            return suffix in SUPPORTED_INPUTS or suffix in SUPPORTED_VIDEO_INPUTS or suffix in AUDIO_INPUT_EXTENSIONS

        return True


class FileRenamerPage(ToolPage):
    def __init__(self, theme_provider):
        super().__init__("File Renamer", "Copy files into a clean numbered sequence with optional output batches.", theme_provider)
        self.io = Card("Input and output")
        self.input_folder = PathPicker("Input folder", "Folder containing files to copy and rename.")
        self.output_folder = PathPicker("Output folder", "Folder where renamed files will be written.")
        self.include_subfolders = QCheckBox("Include subfolders")
        self.io.body_layout.addWidget(self.input_folder)
        self.io.body_layout.addWidget(self.output_folder)
        self.io.body_layout.addWidget(self.include_subfolders)
        self.content_layout.addWidget(self.io)

        self.settings = Card("Rename settings")
        holder = QWidget()
        grid = make_grid(holder)
        self.file_filter = combo(FILE_FILTERS, FILE_FILTER_ALL)
        self.sort_mode = combo(SORT_MODES, SORT_NAME_ASC)
        self.rename_mode = combo(RENAME_MODES, RENAME_GLOBAL)
        self.numbering_source = combo(NUMBERING_SOURCES, NUMBERING_INTERNAL)
        self.start_number = line("1", integer=True)
        self.padding = line("0", integer=True)
        self.prefix = line("")
        self.preserve_extension = QCheckBox("Preserve file extensions")
        self.preserve_extension.setChecked(True)
        row = 0
        row = add_grid_row(grid, row, "File filter", self.file_filter)
        row = add_grid_row(grid, row, "Sort order", self.sort_mode)
        row = add_grid_row(grid, row, RENAMING_MODE, self.rename_mode)
        row = add_grid_row(grid, row, NUMBERING_SOURCE, self.numbering_source)
        row = add_grid_row(grid, row, STARTING_NUMBER, self.start_number)
        row = add_grid_row(grid, row, PADDING, self.padding)
        row = add_grid_row(grid, row, PREFIX, self.prefix)
        add_grid_row(grid, row, EXTENSIONS, self.preserve_extension)
        self.settings.body_layout.addWidget(holder)
        self.content_layout.addWidget(self.settings)

        self.batch_options = BatchOptions(count_label="Files per folder")
        self.content_layout.addWidget(self.batch_options)

        self.preview = Card("Preview")
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMinimumHeight(150)
        self.preview.body_layout.addWidget(self.preview_text)
        preview_btn = make_button("Refresh Preview")
        preview_btn.clicked.connect(self._refresh_preview)
        self.preview.body_layout.addWidget(preview_btn)
        self.content_layout.addWidget(self.preview)
        self.content_layout.addStretch(1)

        self.input_folder.button.clicked.connect(self._choose_input_folder)
        self.output_folder.button.clicked.connect(self._choose_output_folder)
        self.add_action("Rename Files", self._start)

    def _choose_input_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose input folder")
        if folder:
            self.input_folder.set_path(folder)
            if not self.output_folder.path():
                path = Path(folder)
                self.output_folder.set_path(path.parent / f"{path.name}_renamed")

    def _choose_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if folder:
            self.output_folder.set_path(folder)

    def _snapshot(self) -> dict:
        return {
            "input_folder": self.input_folder.path(),
            "output_folder": self.output_folder.path(),
            "include_subfolders": self.include_subfolders.isChecked(),
            "file_filter": self.file_filter.currentText(),
            "sort_mode": self.sort_mode.currentText(),
            "rename_mode": self.rename_mode.currentText(),
            "numbering_source": self.numbering_source.currentText(),
            "starting_number": parse_starting_number(self.start_number.text()),
            "padding": parse_padding(self.padding.text()),
            "prefix": self.prefix.text().strip(),
            "preserve_extension": self.preserve_extension.isChecked(),
            "batch": self.batch_options.snapshot(),
        }

    def _refresh_preview(self):
        try:
            s = self._snapshot()
            input_dir = Path(s["input_folder"])
            output_dir = Path(s["output_folder"]) if s["output_folder"] else None
            if not input_dir.is_dir():
                self.preview_text.setPlainText("Choose a valid input folder.")
                return
            files = get_renamable_files(input_dir, s["include_subfolders"], s["file_filter"], output_dir)
            files = sort_files(files, s["sort_mode"])
            target_dir_for_item = self._rename_target_dir_provider(output_dir, s["batch"]) if output_dir else None
            preview = preview_names(
                files,
                s["starting_number"],
                s["padding"],
                s["preserve_extension"],
                s["rename_mode"],
                s["prefix"],
                s["numbering_source"],
                output_dir,
                target_dir_for_item,
            )
            lines = [f"Ready: {len(files)} file(s)", ""]
            lines.extend(f"{path.name} -> {name}" for path, name in preview[:160])
            self.preview_text.setPlainText("\n".join(lines))
        except Exception as exc:
            self.preview_text.setPlainText(str(exc))

    def _start(self):
        try:
            self.start_worker(self._snapshot())
        except ValueError:
            show_message(self, "Error", "Rename settings must be valid whole numbers.", self.theme(), "error")

    def run_task(self, s: dict):
        input_dir = Path(s["input_folder"])
        output_dir = Path(s["output_folder"])
        if not input_dir.is_dir():
            self.post("error", "Choose a valid input folder.")
            return
        if not s["output_folder"]:
            self.post("error", "Choose a valid output folder.")
            return
        files = get_renamable_files(input_dir, s["include_subfolders"], s["file_filter"], output_dir)
        files = sort_files(files, s["sort_mode"])
        if not files:
            self.post("error", "No files found for the current settings.")
            return
        plan = build_rename_plan(
            files,
            s["starting_number"],
            s["padding"],
            s["preserve_extension"],
            s["rename_mode"],
            s["prefix"],
            s["numbering_source"],
            output_dir,
            self._rename_target_dir_provider(output_dir, s["batch"]),
        )
        self.post("progress", 0, len(files))
        state = {"size": 0, "count": 0, "index": 1}
        success = 0
        for idx, item in enumerate(plan, start=1):
            file = item.source
            self.post("status", f"Renaming {idx}/{len(files)}", file.name)
            out_path = None
            try:
                if s["batch"]["enabled"] and s["batch"]["method"] == BATCH_BY_COUNT:
                    target_dir = get_batch_folder(output_dir, idx, s["batch"]["batch_size"])
                elif s["batch"]["enabled"]:
                    next_size = file.stat().st_size
                    if should_start_new_size_batch(state["size"], next_size, s["batch"]["max_bytes"], state["count"]):
                        state["index"] += 1
                        state["size"] = 0
                        state["count"] = 0
                    target_dir = get_batch_folder_by_index(output_dir, state["index"])
                else:
                    target_dir = output_dir
                out_path = copy_rename_plan_item(item, target_dir)
                if s["batch"]["enabled"] and s["batch"]["method"] == BATCH_BY_SIZE:
                    state["size"] += out_path.stat().st_size
                    state["count"] += 1
                self.post("log", f"OK   {file.name} -> {out_path.relative_to(output_dir)}", "ok")
                success += 1
            except Exception as exc:
                if out_path and out_path.exists():
                    out_path.unlink()
                self.post("log", f"FAIL {file.name}: {exc}", "err")
            self.post("progress", idx, len(files))
        self.post("done", f"Renamed {success} of {len(files)} file(s).", "Renaming complete. Check the output folder.")

    def _rename_target_dir_provider(self, output_dir: Path, batch: dict):
        state = {"size": 0, "count": 0, "index": 1}

        def target_dir(index: int, file: Path) -> Path:
            if not batch["enabled"]:
                return output_dir

            if batch["method"] == BATCH_BY_COUNT:
                batch_index = ((index - 1) // max(1, batch["batch_size"])) + 1
                return batch_folder_path(output_dir, batch_index)

            next_size = file.stat().st_size
            if should_start_new_size_batch(state["size"], next_size, batch["max_bytes"], state["count"]):
                state["index"] += 1
                state["size"] = 0
                state["count"] = 0

            current = batch_folder_path(output_dir, state["index"])
            state["size"] += next_size
            state["count"] += 1
            return current

        return target_dir
