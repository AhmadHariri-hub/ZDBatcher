from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QWidget

from app.core.audio_converter import (
    FILTER_AUDIO_ONLY,
    INPUT_TYPE_FILTERS,
    OUTPUT_AUDIO_FORMATS,
    QUALITY_BALANCED as AUDIO_QUALITY_BALANCED,
    QUALITY_PRESETS as AUDIO_QUALITY_PRESETS,
)
from app.core.batcher import (
    BATCH_BY_COUNT,
    BATCH_BY_SIZE,
    BATCH_METHODS,
    parse_batch_size,
    parse_folder_size_mb,
)
from app.core.file_sorter import (
    FOLDER_STRUCTURES,
    MEDIA_AUDIO as SORT_MEDIA_AUDIO,
    MEDIA_IMAGES as SORT_MEDIA_IMAGES,
    MEDIA_VIDEOS as SORT_MEDIA_VIDEOS,
)
from app.core.image_converter import get_output_formats
from app.core.image_resizer import (
    RESIZE_BY_HEIGHT as IMAGE_RESIZE_BY_HEIGHT,
    RESIZE_BY_WIDTH as IMAGE_RESIZE_BY_WIDTH,
    RESIZE_EXACT as IMAGE_RESIZE_EXACT,
    RESIZE_MODES as IMAGE_RESIZE_MODES,
    RESIZE_PERCENT as IMAGE_RESIZE_PERCENT,
    parse_optional_max_bytes as parse_image_optional_max_bytes,
    parse_percentage as parse_image_percentage,
    parse_positive_int as parse_image_positive_int,
)
from app.core.media_engine import find_ffmpeg
from app.core.renamer import NUMBERING_INTERNAL, NUMBERING_SOURCES, RENAME_GLOBAL, RENAME_MODES, parse_padding, parse_starting_number
from app.core.video_converter import (
    GIF_FPS_OPTIONS,
    GIF_FPS_ORIGINAL,
    GIF_WIDTH_CUSTOM,
    GIF_WIDTH_KEEP,
    GIF_WIDTH_OPTIONS,
    OUTPUT_VIDEO_FORMATS,
    QUALITY_BALANCED as VIDEO_QUALITY_BALANCED,
    RESIZE_KEEP as VIDEO_CONVERT_RESIZE_KEEP,
)
from app.core.video_resizer import (
    PRESET_1080,
    PRESET_RESOLUTIONS,
    RESIZE_CUSTOM as VIDEO_RESIZE_CUSTOM,
    RESIZE_MODES as VIDEO_RESIZE_MODES,
    RESIZE_PERCENT as VIDEO_RESIZE_PERCENT,
    RESIZE_PRESET as VIDEO_RESIZE_PRESET,
    parse_optional_target_bytes as parse_video_optional_target_bytes,
    parse_percentage as parse_video_percentage,
    parse_positive_int as parse_video_positive_int,
)
from app.core.watch_folder import (
    EVENT_CURRENT,
    EVENT_LOG,
    EVENT_PROGRESS,
    EVENT_QUEUE,
    EVENT_STATUS,
    STATUS_PROCESSING,
    STATUS_STOPPED,
    STATUS_WATCHING,
    AudioRules,
    BatchRules,
    ImageRules,
    RenamingRules,
    SortingRules,
    VideoRules,
    WatchFolderService,
    WatchSettings,
)
from app.ui.qt_pages import ToolPage, add_grid_row, combo, grid_row_widgets, line, make_grid
from app.ui.qt_widgets import AppCheckBox as QCheckBox
from app.ui.qt_widgets import Card, PathPicker, make_button, make_label, show_message
from app.ui.tool_labels import (
    BATCH_METHOD,
    CUSTOM_GIF_WIDTH,
    EXTENSIONS,
    FILES_PER_FOLDER,
    FOLDER_STRUCTURE,
    GIF_FPS,
    GIF_WIDTH,
    HEIGHT,
    INPUT_FILTER,
    MAX_FOLDER_SIZE,
    MAX_MB,
    MEDIA_TYPES,
    NUMBERING_SOURCE,
    OUTPUT_FORMAT,
    PADDING,
    PERCENTAGE,
    PRESET,
    PREFIX,
    QUALITY,
    RENAMING_MODE,
    RESIZE,
    RESIZE_MODE,
    SIZE_LIMIT,
    STARTING_NUMBER,
    TARGET_MB,
    TARGET_SIZE,
    WIDTH,
)


class WatchSection(Card):
    def __init__(self, title: str, subtitle: str = ""):
        super().__init__()
        self.toggle = QCheckBox(title)
        self.layout.insertWidget(0, self.toggle)

        if subtitle:
            self.layout.insertWidget(1, make_label(subtitle, muted=True))

        self.body.setVisible(False)
        self.toggle.toggled.connect(self.body.setVisible)

    def isChecked(self) -> bool:
        return self.toggle.isChecked()


class WatchFolderPage(ToolPage):
    def __init__(self, theme_provider):
        super().__init__(
            "Watch Folder",
            "Automatically process files when they are added to a folder.",
            theme_provider,
        )
        self.service = WatchFolderService(self._on_watch_event)
        self.queue_count = 0
        self.current_file = ""
        self.watch_status = STATUS_STOPPED

        self._build_status_pill()
        self._build_locations()
        self._build_image_conversion()
        self._build_image_resizer()
        self._build_video_converter()
        self._build_video_resizer()
        self._build_audio_converter()
        self._build_file_sorter()
        self._build_file_renamer()
        self._build_batch_output()
        self.content_layout.addStretch(1)

        self._build_action_controls()
        self._sync_controls()
        self._set_watch_status(STATUS_STOPPED, "Choose folders and rules, then start watching.")
        self.log_line("Media engine ready" if find_ffmpeg() else "Media engine unavailable", "ok" if find_ffmpeg() else "err")

    def _build_status_pill(self):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        label = make_label("Status")
        label.setStyleSheet("font-weight: 700;")
        self.status_pill = make_label(STATUS_STOPPED, role="pill")
        layout.addWidget(label)
        layout.addWidget(self.status_pill)
        layout.addStretch(1)
        self.content_layout.addWidget(row)

    def _build_locations(self):
        self.locations = Card("Watch locations")
        self.input_folder = PathPicker("Input folder", "Folder to monitor for new files.")
        self.output_folder = PathPicker("Output folder", "Folder where processed files will be written.")
        self.include_subfolders = QCheckBox("Include subfolders")
        self.process_existing = QCheckBox("Process existing files on start")
        self.locations.body_layout.addWidget(self.input_folder)
        self.locations.body_layout.addWidget(self.output_folder)
        self.locations.body_layout.addWidget(self.include_subfolders)
        self.locations.body_layout.addWidget(self.process_existing)
        self.content_layout.addWidget(self.locations)

        self.input_folder.button.clicked.connect(self._choose_input_folder)
        self.output_folder.button.clicked.connect(self._choose_output_folder)

    def _build_image_conversion(self):
        self.image_conversion = WatchSection("Image Conversion")
        holder = QWidget()
        grid = make_grid(holder)
        self.image_convert_format = combo(get_output_formats(), "jpg")
        add_grid_row(grid, 0, OUTPUT_FORMAT, self.image_convert_format)
        self.image_conversion.body_layout.addWidget(holder)
        self.content_layout.addWidget(self.image_conversion)
        self.image_conversion.toggle.toggled.connect(self._sync_controls)

    def _build_image_resizer(self):
        self.image_resizer = WatchSection("Image Resizer")
        holder = QWidget()
        grid = make_grid(holder)
        self.image_resize_mode = combo(IMAGE_RESIZE_MODES, IMAGE_RESIZE_BY_WIDTH)
        self.image_width = line("1200", integer=True)
        self.image_height = line("800", integer=True)
        self.image_percentage = line("50", decimal=True)
        self.image_max_size_enabled = QCheckBox("Target max file size")
        self.image_max_mb = line("3", decimal=True)
        row = 0
        row = add_grid_row(grid, row, RESIZE_MODE, self.image_resize_mode)
        row = add_grid_row(grid, row, WIDTH, self.image_width)
        row = add_grid_row(grid, row, HEIGHT, self.image_height)
        row = add_grid_row(grid, row, PERCENTAGE, self.image_percentage)
        row = add_grid_row(grid, row, SIZE_LIMIT, self.image_max_size_enabled)
        add_grid_row(grid, row, MAX_MB, self.image_max_mb)
        self.image_resizer.body_layout.addWidget(holder)
        self.content_layout.addWidget(self.image_resizer)

        self.image_resizer.toggle.toggled.connect(self._sync_controls)
        self.image_resize_mode.currentTextChanged.connect(self._sync_controls)
        self.image_max_size_enabled.toggled.connect(self._sync_controls)

    def _build_video_converter(self):
        self.video_converter = WatchSection("Video Converter")
        holder = QWidget()
        grid = make_grid(holder)
        self.video_convert_format = combo(OUTPUT_VIDEO_FORMATS, "mp4")
        self.gif_fps = combo(GIF_FPS_OPTIONS, GIF_FPS_ORIGINAL)
        self.gif_width = combo(GIF_WIDTH_OPTIONS, GIF_WIDTH_KEEP)
        self.gif_custom_width = line("", integer=True)
        row = 0
        row = add_grid_row(grid, row, OUTPUT_FORMAT, self.video_convert_format)
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
        self.video_converter.body_layout.addWidget(holder)
        self.content_layout.addWidget(self.video_converter)

        self.video_converter.toggle.toggled.connect(self._sync_controls)
        self.video_convert_format.currentTextChanged.connect(self._sync_controls)
        self.gif_width.currentTextChanged.connect(self._sync_controls)

    def _build_video_resizer(self):
        self.video_resizer = WatchSection("Video Resizer")
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
        self.video_resizer.body_layout.addWidget(holder)
        self.content_layout.addWidget(self.video_resizer)

        self.video_resizer.toggle.toggled.connect(self._sync_controls)
        self.video_resize_mode.currentTextChanged.connect(self._sync_controls)
        self.video_target_enabled.toggled.connect(self._sync_controls)

    def _build_audio_converter(self):
        self.audio_converter = WatchSection("Audio Converter")
        holder = QWidget()
        grid = make_grid(holder)
        self.audio_input_filter = combo(INPUT_TYPE_FILTERS, FILTER_AUDIO_ONLY)
        self.audio_format = combo(OUTPUT_AUDIO_FORMATS, "mp3")
        self.audio_quality = combo(AUDIO_QUALITY_PRESETS, AUDIO_QUALITY_BALANCED)
        row = 0
        row = add_grid_row(grid, row, INPUT_FILTER, self.audio_input_filter)
        row = add_grid_row(grid, row, OUTPUT_FORMAT, self.audio_format)
        add_grid_row(grid, row, QUALITY, self.audio_quality)
        self.audio_converter.body_layout.addWidget(holder)
        self.content_layout.addWidget(self.audio_converter)
        self.audio_converter.toggle.toggled.connect(self._sync_controls)

    def _build_file_sorter(self):
        self.file_sorter = WatchSection("File Sorter")
        holder = QWidget()
        grid = make_grid(holder)
        self.sort_structure = combo(FOLDER_STRUCTURES)
        self.sort_images = QCheckBox("Images")
        self.sort_videos = QCheckBox("Videos")
        self.sort_audio = QCheckBox("Audio")
        for check in (self.sort_images, self.sort_videos, self.sort_audio):
            check.setChecked(True)
        checks = QWidget()
        check_layout = QHBoxLayout(checks)
        check_layout.setContentsMargins(0, 0, 0, 0)
        check_layout.addWidget(self.sort_images)
        check_layout.addWidget(self.sort_videos)
        check_layout.addWidget(self.sort_audio)
        row = 0
        row = add_grid_row(grid, row, FOLDER_STRUCTURE, self.sort_structure)
        add_grid_row(grid, row, MEDIA_TYPES, checks)
        self.file_sorter.body_layout.addWidget(holder)
        self.content_layout.addWidget(self.file_sorter)
        self.file_sorter.toggle.toggled.connect(self._sync_controls)

    def _build_file_renamer(self):
        self.file_renamer = WatchSection("File Renamer")
        holder = QWidget()
        grid = make_grid(holder)
        self.rename_mode = combo(RENAME_MODES, RENAME_GLOBAL)
        self.numbering_source = combo(NUMBERING_SOURCES, NUMBERING_INTERNAL)
        self.rename_start = line("1", integer=True)
        self.rename_padding = line("0", integer=True)
        self.rename_prefix = line("")
        self.rename_preserve = QCheckBox("Preserve file extensions")
        self.rename_preserve.setChecked(True)
        row = 0
        row = add_grid_row(grid, row, RENAMING_MODE, self.rename_mode)
        row = add_grid_row(grid, row, NUMBERING_SOURCE, self.numbering_source)
        row = add_grid_row(grid, row, STARTING_NUMBER, self.rename_start)
        row = add_grid_row(grid, row, PADDING, self.rename_padding)
        row = add_grid_row(grid, row, PREFIX, self.rename_prefix)
        add_grid_row(grid, row, EXTENSIONS, self.rename_preserve)
        self.file_renamer.body_layout.addWidget(holder)
        self.content_layout.addWidget(self.file_renamer)
        self.file_renamer.toggle.toggled.connect(self._sync_controls)

    def _build_batch_output(self):
        self.batch_output = WatchSection("Batch Output")
        holder = QWidget()
        grid = make_grid(holder)
        self.batch_method = combo(BATCH_METHODS, BATCH_BY_COUNT)
        self.batch_count = line("40", integer=True)
        self.batch_max_mb = line("100", decimal=True)
        row = 0
        row = add_grid_row(grid, row, BATCH_METHOD, self.batch_method)
        row = add_grid_row(grid, row, FILES_PER_FOLDER, self.batch_count)
        add_grid_row(grid, row, MAX_FOLDER_SIZE, self.batch_max_mb)
        self.batch_output.body_layout.addWidget(holder)
        self.content_layout.addWidget(self.batch_output)
        self.batch_output.toggle.toggled.connect(self._sync_controls)
        self.batch_method.currentTextChanged.connect(self._sync_controls)

    def _build_action_controls(self):
        self.start_button = make_button("Start Watching", "primary")
        self.stop_button = make_button("Stop Watching")
        self.clear_button = make_button("Clear Queue")
        self.start_button.clicked.connect(self._start_watching)
        self.stop_button.clicked.connect(self._stop_watching)
        self.clear_button.clicked.connect(self._clear_queue)
        self.action_slot.addWidget(self.start_button)
        self.action_slot.addWidget(self.stop_button)
        self.action_slot.addWidget(self.clear_button)
        self.stop_button.setEnabled(False)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)

    def _choose_input_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose watch input folder")
        if folder:
            self.input_folder.set_path(folder)
            if not self.output_folder.path():
                path = Path(folder)
                self.output_folder.set_path(path.parent / f"{path.name}_watch_output")

    def _choose_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose watch output folder")
        if folder:
            self.output_folder.set_path(folder)

    def _start_watching(self):
        try:
            settings = self._snapshot()
            self.service.start(settings)
        except Exception as exc:
            show_message(self, "Watch Folder", str(exc), self.theme(), "error")

    def _stop_watching(self):
        self.service.stop()

    def _clear_queue(self):
        self.service.clear_queue()

    def _snapshot(self) -> WatchSettings:
        input_folder = self.input_folder.path()
        output_folder = self.output_folder.path()

        if not input_folder:
            raise ValueError("Choose a valid input folder.")

        if not output_folder:
            raise ValueError("Choose a valid output folder.")

        image_resize_enabled = self.image_resizer.isChecked()
        image_resize_mode = self.image_resize_mode.currentText()
        video_resize_enabled = self.video_resizer.isChecked()
        video_resize_mode = self.video_resize_mode.currentText()
        video_converter_enabled = self.video_converter.isChecked()

        image_rules = ImageRules(
            convert=self.image_conversion.isChecked(),
            convert_output_format=self.image_convert_format.currentText().lower(),
            resize=image_resize_enabled,
            resize_mode=image_resize_mode,
            width=parse_image_positive_int(self.image_width.text(), WIDTH) if image_resize_enabled and image_resize_mode in {IMAGE_RESIZE_BY_WIDTH, IMAGE_RESIZE_EXACT} else None,
            height=parse_image_positive_int(self.image_height.text(), HEIGHT) if image_resize_enabled and image_resize_mode in {IMAGE_RESIZE_BY_HEIGHT, IMAGE_RESIZE_EXACT} else None,
            percentage=parse_image_percentage(self.image_percentage.text()) if image_resize_enabled and image_resize_mode == IMAGE_RESIZE_PERCENT else None,
            max_bytes=parse_image_optional_max_bytes(self.image_max_mb.text()) if image_resize_enabled and self.image_max_size_enabled.isChecked() else None,
        )

        video_rules = VideoRules(
            convert=video_converter_enabled,
            convert_output_format=self.video_convert_format.currentText().lower(),
            convert_quality_preset=VIDEO_QUALITY_BALANCED,
            convert_resize_option=VIDEO_CONVERT_RESIZE_KEEP,
            gif_fps=self.gif_fps.currentText(),
            gif_width_option=self.gif_width.currentText(),
            gif_custom_width=self._gif_custom_width() if video_converter_enabled else None,
            resize=video_resize_enabled,
            resize_mode=video_resize_mode,
            preset_resolution=self.video_preset.currentText(),
            width=parse_video_positive_int(self.video_width.text(), WIDTH) if video_resize_enabled and video_resize_mode == VIDEO_RESIZE_CUSTOM else None,
            height=parse_video_positive_int(self.video_height.text(), HEIGHT) if video_resize_enabled and video_resize_mode == VIDEO_RESIZE_CUSTOM else None,
            percentage=parse_video_percentage(self.video_percentage.text()) if video_resize_enabled and video_resize_mode == VIDEO_RESIZE_PERCENT else None,
            target_bytes=parse_video_optional_target_bytes(self.video_target_mb.text()) if video_resize_enabled and self.video_target_enabled.isChecked() else None,
            resize_quality_preset=VIDEO_QUALITY_BALANCED,
        )

        audio_rules = AudioRules(
            enabled=self.audio_converter.isChecked(),
            input_filter=self.audio_input_filter.currentText(),
            output_format=self.audio_format.currentText().lower(),
            quality_preset=self.audio_quality.currentText(),
        )

        sorting_rules = SortingRules(
            enabled=self.file_sorter.isChecked(),
            folder_structure=self.sort_structure.currentText(),
            media_types=frozenset(self._sort_media_types()),
        )

        renaming_rules = RenamingRules(
            enabled=self.file_renamer.isChecked(),
            numbering_mode=self.rename_mode.currentText(),
            numbering_source=self.numbering_source.currentText(),
            starting_number=parse_starting_number(self.rename_start.text()) if self.file_renamer.isChecked() else 1,
            padding=parse_padding(self.rename_padding.text()) if self.file_renamer.isChecked() else 0,
            prefix=self.rename_prefix.text().strip(),
            preserve_extension=self.rename_preserve.isChecked(),
        )

        batch_method = self.batch_method.currentText()
        batch_rules = BatchRules(
            enabled=self.batch_output.isChecked(),
            method=batch_method,
            files_per_folder=parse_batch_size(self.batch_count.text()) if self.batch_output.isChecked() and batch_method == BATCH_BY_COUNT else 40,
            max_folder_bytes=parse_folder_size_mb(self.batch_max_mb.text()) if self.batch_output.isChecked() and batch_method == BATCH_BY_SIZE else 100_000_000,
        )

        return WatchSettings(
            input_folder=Path(input_folder),
            output_folder=Path(output_folder),
            include_subfolders=self.include_subfolders.isChecked(),
            process_existing=self.process_existing.isChecked(),
            image=image_rules,
            video=video_rules,
            audio=audio_rules,
            sorting=sorting_rules,
            renaming=renaming_rules,
            batch=batch_rules,
        )

    def _gif_custom_width(self) -> int | None:
        if self.video_convert_format.currentText().lower() != "gif" or self.gif_width.currentText() != GIF_WIDTH_CUSTOM:
            return None

        if not self.gif_custom_width.text().strip():
            raise ValueError("Custom GIF width is required.")

        return parse_video_positive_int(self.gif_custom_width.text(), CUSTOM_GIF_WIDTH)

    def _sort_media_types(self) -> set[str]:
        enabled = set()

        if self.sort_images.isChecked():
            enabled.add(SORT_MEDIA_IMAGES)

        if self.sort_videos.isChecked():
            enabled.add(SORT_MEDIA_VIDEOS)

        if self.sort_audio.isChecked():
            enabled.add(SORT_MEDIA_AUDIO)

        return enabled

    def _sync_controls(self, *_args):
        image_resize_enabled = self.image_resizer.isChecked()
        image_mode = self.image_resize_mode.currentText()
        self.image_width.setEnabled(image_resize_enabled and image_mode in {IMAGE_RESIZE_BY_WIDTH, IMAGE_RESIZE_EXACT})
        self.image_height.setEnabled(image_resize_enabled and image_mode in {IMAGE_RESIZE_BY_HEIGHT, IMAGE_RESIZE_EXACT})
        self.image_percentage.setEnabled(image_resize_enabled and image_mode == IMAGE_RESIZE_PERCENT)
        self.image_max_size_enabled.setEnabled(image_resize_enabled)
        self.image_max_mb.setEnabled(image_resize_enabled and self.image_max_size_enabled.isChecked())

        video_converter_enabled = self.video_converter.isChecked()
        video_is_gif = self.video_convert_format.currentText().lower() == "gif"
        show_gif_options = video_converter_enabled and video_is_gif
        show_custom_width = show_gif_options and self.gif_width.currentText() == GIF_WIDTH_CUSTOM
        for row in self.gif_rows:
            for widget in row:
                widget.setVisible(show_gif_options)
                widget.setEnabled(show_gif_options)
        for widget in self.gif_custom_width_row:
            widget.setVisible(show_custom_width)
            widget.setEnabled(show_custom_width)

        video_resize_enabled = self.video_resizer.isChecked()
        video_mode = self.video_resize_mode.currentText()
        self.video_preset.setEnabled(video_resize_enabled and video_mode == VIDEO_RESIZE_PRESET)
        self.video_width.setEnabled(video_resize_enabled and video_mode == VIDEO_RESIZE_CUSTOM)
        self.video_height.setEnabled(video_resize_enabled and video_mode == VIDEO_RESIZE_CUSTOM)
        self.video_percentage.setEnabled(video_resize_enabled and video_mode == VIDEO_RESIZE_PERCENT)
        self.video_target_enabled.setEnabled(video_resize_enabled)
        self.video_target_mb.setEnabled(video_resize_enabled and self.video_target_enabled.isChecked())

        batch_enabled = self.batch_output.isChecked()
        self.batch_method.setEnabled(batch_enabled)
        self.batch_count.setEnabled(batch_enabled and self.batch_method.currentText() == BATCH_BY_COUNT)
        self.batch_max_mb.setEnabled(batch_enabled and self.batch_method.currentText() == BATCH_BY_SIZE)

    def _on_watch_event(self, event: dict):
        self.post("watch_event", event)

    def _handle_event(self, item):
        if item[0] == "watch_event":
            self._handle_watch_event(item[1])
            return

        super()._handle_event(item)

    def _handle_watch_event(self, event: dict):
        kind = event.get("kind")

        if kind == EVENT_LOG:
            self.log_line(event.get("text", ""), event.get("tag", ""))
        elif kind == EVENT_STATUS:
            self._set_watch_status(event.get("status", STATUS_STOPPED), event.get("message", ""))
        elif kind == EVENT_QUEUE:
            self.queue_count = int(event.get("count", 0))
            self._refresh_status_subtitle()
        elif kind == EVENT_CURRENT:
            self.current_file = event.get("name", "")
            self._refresh_status_subtitle()
        elif kind == EVENT_PROGRESS:
            self.progress_bar.setRange(0, max(1, int(event.get("maximum", 1))))
            self.progress_bar.setValue(int(event.get("value", 0)))

    def _set_watch_status(self, status: str, message: str = ""):
        self.watch_status = status
        self.status_pill.setText(status)
        self.status_label.setText(status)
        self._refresh_status_subtitle(message)
        running = status in {STATUS_WATCHING, STATUS_PROCESSING}
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)

    def _refresh_status_subtitle(self, message: str = ""):
        current = self.current_file or "None"
        details = f"Queue: {self.queue_count} | Current: {current}"
        self.status_subtitle.setText(f"{message}  {details}" if message else details)

    def shutdown(self):
        self.service.stop()
