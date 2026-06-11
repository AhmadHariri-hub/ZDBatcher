import sys

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QProgressBar,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

import app.config as app_config
from app.config import APP_NAME
from app.core.ffmpeg_installer import FFMPEG_ARCHIVE_URL, FfmpegInstallError, InstallProgress, install_ffmpeg
from app.core.media_engine import find_ffmpeg, find_ffprobe
from app.ui.qt_pages import (
    AudioConverterPage,
    BatchFoldersPage,
    FileRenamerPage,
    FileSorterPage,
    ImageConversionPage,
    ImageResizerPage,
    MixedMediaPage,
    MixedMediaResizerPage,
    VideoConverterPage,
    VideoResizerPage,
)
from app.ui.tabs.watch_folder_tab import WatchFolderPage
from app.ui.qt_theme import get_theme, stylesheet
from app.ui.qt_widgets import SupportDialog, ask_confirm, make_button, make_label, set_role, show_message


class FfmpegInstallThread(QThread):
    progress = Signal(object)
    succeeded = Signal(str, str)
    failed = Signal(str)

    def run(self):
        try:
            ffmpeg_path, ffprobe_path = install_ffmpeg(self.progress.emit)
            find_ffmpeg.cache_clear()
            find_ffprobe.cache_clear()
            self.succeeded.emit(str(ffmpeg_path), str(ffprobe_path))
        except FfmpegInstallError as exc:
            self.failed.emit(str(exc))
        except Exception:
            self.failed.emit("FFmpeg installation failed unexpectedly. Please try the PowerShell installer instead.")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.mode = app_config.get_theme_mode()
        self.theme = get_theme(self.mode)
        self.nav_buttons = {}
        self.pages = {}
        self.ffmpeg_install_thread: FfmpegInstallThread | None = None

        self.setWindowTitle(APP_NAME)
        self.resize(1440, 980)
        self.setMinimumSize(1120, 760)

        self.root = QWidget()
        self.root.setObjectName("AppRoot")
        self.setCentralWidget(self.root)

        self.layout = QHBoxLayout(self.root)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self._build_sidebar()
        self._build_main()
        self._apply_theme()
        self.show_page("image")

    def _build_sidebar(self):
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(260)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 24, 18, 20)
        layout.setSpacing(8)

        title = QLabel(APP_NAME)
        title.setStyleSheet("font-size: 22pt; font-weight: 800;")
        subtitle = make_label("Modern batch media tools", muted=True)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(6)

        divider = QFrame()
        divider.setObjectName("Divider")
        layout.addWidget(divider)
        layout.addSpacing(4)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        tools = [
            ("image", "Image Conversion"),
            ("image_resizer", "Image Resizer"),
            ("video", "Video Converter"),
            ("video_resizer", "Video Resizer"),
            ("audio", "Audio Converter"),
            ("mixed", "Mixed Media Converter"),
            ("mixed_resizer", "Mixed Media Resizer"),
            ("sorter", "File Sorter"),
            ("batch", "Batch Folders"),
            ("rename", "File Renamer"),
            ("watch", "\u2605 Watch Folder"),
        ]

        for index, (key, label) in enumerate(tools):
            button = make_button(label, "nav", checkable=True)
            button.setMinimumHeight(40)
            button.clicked.connect(lambda checked=False, page_key=key: self.show_page(page_key))
            self.nav_group.addButton(button, index)
            self.nav_buttons[key] = button
            layout.addWidget(button)

        layout.addStretch(1)
        self.ffmpeg_footer = QWidget()
        footer_layout = QVBoxLayout(self.ffmpeg_footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(8)

        self.ffmpeg_status = make_label("FFmpeg required", muted=True)
        set_role(self.ffmpeg_status, sidebarFooter=True)
        footer_layout.addWidget(self.ffmpeg_status)

        self.ffmpeg_progress_label = make_label("", muted=True)
        set_role(self.ffmpeg_progress_label, sidebarFooter=True)
        self.ffmpeg_progress_label.hide()
        footer_layout.addWidget(self.ffmpeg_progress_label)

        self.ffmpeg_install_button = make_button("Install FFmpeg", "primary")
        self.ffmpeg_install_button.clicked.connect(self._confirm_ffmpeg_install)
        footer_layout.addWidget(self.ffmpeg_install_button)

        self.ffmpeg_progress = QProgressBar()
        self.ffmpeg_progress.setRange(0, 0)
        self.ffmpeg_progress.setTextVisible(False)
        self.ffmpeg_progress.hide()
        footer_layout.addWidget(self.ffmpeg_progress)

        layout.addWidget(self.ffmpeg_footer)
        self.layout.addWidget(sidebar)
        self._refresh_ffmpeg_footer()

    def _build_main(self):
        host = QWidget()
        host.setObjectName("PageHost")
        host_layout = QVBoxLayout(host)
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("AppHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 20, 24, 14)
        header_layout.setSpacing(12)

        self.header_title = QLabel("Image Conversion")
        self.header_title.setStyleSheet("font-size: 15pt; font-weight: 700;")
        self.header_subtitle = make_label("Convert, resize, organize, and prepare media cleanly.", muted=True)

        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(4)
        title_box.addWidget(self.header_title)
        title_box.addWidget(self.header_subtitle)
        header_layout.addLayout(title_box, 1)

        self.support_button = make_button("\u2665 Support", "support")
        self.support_button.clicked.connect(self._open_support)
        header_layout.addWidget(self.support_button)

        self.theme_button = make_button("Dark", "segment", checkable=True)
        self.theme_button.setChecked(self.mode == "dark")
        self.theme_button.clicked.connect(self._toggle_theme)
        header_layout.addWidget(self.theme_button)
        host_layout.addWidget(header)

        self.stack = QStackedWidget()
        host_layout.addWidget(self.stack, 1)

        self._register_pages()
        self.layout.addWidget(host, 1)

    def _register_pages(self):
        page_factories = {
            "image": ImageConversionPage,
            "image_resizer": ImageResizerPage,
            "video": VideoConverterPage,
            "video_resizer": VideoResizerPage,
            "audio": AudioConverterPage,
            "mixed": MixedMediaPage,
            "mixed_resizer": MixedMediaResizerPage,
            "watch": WatchFolderPage,
            "sorter": FileSorterPage,
            "batch": BatchFoldersPage,
            "rename": FileRenamerPage,
        }

        for key, factory in page_factories.items():
            page = factory(lambda: self.theme)
            self.pages[key] = page
            self.stack.addWidget(page)

    def show_page(self, key: str):
        page = self.pages[key]
        self.stack.setCurrentWidget(page)
        self.header_title.setText(page.title)
        self.header_subtitle.setText(page.subtitle)
        self.nav_buttons[key].setChecked(True)

    def _toggle_theme(self):
        mode = "dark" if self.theme_button.isChecked() else "light"
        self._set_theme(mode)

    def _set_theme(self, mode: str):
        app_config.set_theme_mode(mode)
        self.mode = mode
        self.theme = get_theme(mode)
        self.theme_button.setText("Dark" if mode == "dark" else "Light")
        self.theme_button.setChecked(mode == "dark")
        self._apply_theme()

    def _apply_theme(self):
        QApplication.instance().setStyleSheet(stylesheet(self.theme))
        self.theme_button.setText("Dark" if self.mode == "dark" else "Light")

    def _open_support(self):
        dialog = SupportDialog(self, self.theme)
        dialog.exec()

    def _has_ffmpeg(self) -> bool:
        find_ffmpeg.cache_clear()
        find_ffprobe.cache_clear()
        return bool(find_ffmpeg() and find_ffprobe())

    def _refresh_ffmpeg_footer(self):
        if self.ffmpeg_install_thread is not None:
            return

        if self._has_ffmpeg():
            self.ffmpeg_status.setText("FFmpeg active")
            self.ffmpeg_progress_label.hide()
            self.ffmpeg_install_button.hide()
            self.ffmpeg_progress.hide()
        else:
            self.ffmpeg_status.setText("FFmpeg required")
            self.ffmpeg_progress_label.hide()
            self.ffmpeg_install_button.show()
            self.ffmpeg_install_button.setEnabled(True)
            self.ffmpeg_progress.hide()

    def _confirm_ffmpeg_install(self):
        if self.ffmpeg_install_thread is not None:
            return

        confirmed = ask_confirm(
            self,
            "Install FFmpeg",
            "ZDBatcher will download FFmpeg and FFprobe into the local tools/ffmpeg folder. Continue?",
            self.theme,
        )

        if confirmed:
            self._start_ffmpeg_install()

    def _start_ffmpeg_install(self):
        self.ffmpeg_status.setText("Installing FFmpeg...")
        self.ffmpeg_progress_label.setText("Starting FFmpeg installer...")
        self.ffmpeg_progress_label.show()
        self.ffmpeg_install_button.setEnabled(False)
        self.ffmpeg_progress.setRange(0, 0)
        self.ffmpeg_progress.show()

        thread = FfmpegInstallThread(self)
        thread.progress.connect(self._on_ffmpeg_install_progress)
        thread.succeeded.connect(self._on_ffmpeg_install_success)
        thread.failed.connect(self._on_ffmpeg_install_failure)
        thread.finished.connect(self._on_ffmpeg_install_finished)
        self.ffmpeg_install_thread = thread
        thread.start()

    def _on_ffmpeg_install_progress(self, progress: InstallProgress):
        self.ffmpeg_status.setText(progress.message)
        self.ffmpeg_progress_label.setText(self._format_ffmpeg_progress(progress))
        self.ffmpeg_progress_label.show()

        if progress.percent is None or progress.indeterminate:
            self.ffmpeg_progress.setRange(0, 0)
        else:
            self.ffmpeg_progress.setRange(0, 100)
            self.ffmpeg_progress.setValue(max(0, min(100, progress.percent)))

    def _on_ffmpeg_install_success(self, ffmpeg_path: str, ffprobe_path: str):
        if self._has_ffmpeg():
            self.ffmpeg_status.setText("FFmpeg active")
            self.ffmpeg_progress_label.setText("FFmpeg installed successfully.")
            self.ffmpeg_install_button.hide()
            show_message(
                self,
                "FFmpeg Installed",
                f"FFmpeg is ready for media tools.\n\n{ffmpeg_path}\n{ffprobe_path}",
                self.theme,
                "info",
            )
            self._refresh_page_ffmpeg_labels()
        else:
            self._on_ffmpeg_install_failure("FFmpeg installed, but ZDBatcher could not detect it. Restart the app and try again.")

    def _on_ffmpeg_install_failure(self, message: str):
        self.ffmpeg_status.setText("FFmpeg required")
        self.ffmpeg_progress_label.setText(message)
        self.ffmpeg_progress_label.show()
        self.ffmpeg_install_button.show()
        self.ffmpeg_install_button.setEnabled(True)
        show_message(
            self,
            "FFmpeg Install Failed",
            f"{message}\n\nYou can also run .\\scripts\\install_ffmpeg.ps1 manually.\n\nSource: {FFMPEG_ARCHIVE_URL}",
            self.theme,
            "error",
        )

    def _on_ffmpeg_install_finished(self):
        if self.ffmpeg_install_thread is not None:
            self.ffmpeg_install_thread.deleteLater()
            self.ffmpeg_install_thread = None
        self.ffmpeg_progress.hide()
        self._refresh_ffmpeg_footer()

    def _format_ffmpeg_progress(self, progress: InstallProgress) -> str:
        if progress.downloaded_bytes and progress.total_bytes and progress.percent is not None:
            return (
                f"Downloading FFmpeg: {progress.percent}% - "
                f"{self._format_mb(progress.downloaded_bytes)} / {self._format_mb(progress.total_bytes)}"
            )

        if progress.downloaded_bytes:
            return f"Downloading FFmpeg: {self._format_mb(progress.downloaded_bytes)} downloaded"

        return progress.message

    def _format_mb(self, byte_count: int) -> str:
        return f"{byte_count / 1_000_000:.1f} MB"

    def _refresh_page_ffmpeg_labels(self):
        active = self._has_ffmpeg()
        labels = {
            "video": "Video engine ready" if active else "Video engine unavailable",
            "video_resizer": "Video engine ready" if active else "Video engine unavailable",
            "audio": "Audio engine ready" if active else "Audio engine unavailable",
            "mixed": "Media engine ready" if active else "Media engine ready for images",
            "mixed_resizer": "Media engine ready" if active else "Media engine ready for images",
        }

        for key, text in labels.items():
            page = self.pages.get(key)
            engine = getattr(page, "engine", None)
            if engine is not None:
                engine.setText(text)

    def closeEvent(self, event):
        if self.ffmpeg_install_thread is not None:
            show_message(
                self,
                "FFmpeg Install Running",
                "FFmpeg is still installing. Please wait for it to finish before closing ZDBatcher.",
                self.theme,
                "info",
            )
            event.ignore()
            return

        for page in self.pages.values():
            shutdown = getattr(page, "shutdown", None)
            if callable(shutdown):
                shutdown()
        super().closeEvent(event)


class ImageConverterApp:
    def __init__(self):
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setStyle("Fusion")
        self.window = MainWindow()

    def run(self):
        self.window.show()
        return self.app.exec()
