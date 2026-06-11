import html
import shutil
import tempfile
import webbrowser
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QTimer, Qt
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QPainter, QPalette, QPen, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyleOptionButton,
    QTextEdit,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_NAME, SUPPORT_URL
from app.ui.qt_theme import Theme


MODE_BATCH = "batch"
MODE_SINGLE = "single"


def set_role(widget: QWidget, **roles):
    for key, value in roles.items():
        widget.setProperty(key, value)
    return widget


def refresh_style(widget: QWidget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def make_button(text: str, variant: str = "", *, checkable: bool = False) -> QPushButton:
    button = AppButton(text)
    if variant:
        set_role(button, variant=variant)
    button.setCheckable(checkable)
    button.setMinimumHeight(38)
    return button


def make_label(text: str, *, muted: bool = False, role: str | None = None) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    if muted:
        set_role(label, muted=True)
    if role:
        set_role(label, **{role: True})
    return label


def _normalize_extensions(extensions) -> set[str]:
    if not extensions:
        return set()

    return {
        str(extension).lower() if str(extension).startswith(".") else f".{str(extension).lower()}"
        for extension in extensions
    }


class Card(QFrame):
    def __init__(self, title: str = "", subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(22, 20, 22, 20)
        self.layout.setSpacing(14)

        if title:
            title_label = make_label(title, role="cardTitle")
            self.layout.addWidget(title_label)

        if subtitle:
            subtitle_label = make_label(subtitle, muted=True)
            self.layout.addWidget(subtitle_label)

        self.body = QWidget()
        self.body.setObjectName("CardBody")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(14)
        self.layout.addWidget(self.body)


class AppLineEdit(QLineEdit):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._sync_cursor()

    def setEnabled(self, enabled: bool):
        super().setEnabled(enabled)
        self._sync_cursor()

    def changeEvent(self, event):
        super().changeEvent(event)
        self._sync_cursor()

    def _sync_cursor(self):
        self.setCursor(Qt.IBeamCursor if self.isEnabled() and not self.isReadOnly() else Qt.ArrowCursor)

    def setReadOnly(self, read_only: bool):
        super().setReadOnly(read_only)
        self._sync_cursor()


class DropPathLineEdit(AppLineEdit):
    def __init__(self, picker, parent=None):
        super().__init__("", parent)
        self._picker = picker
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        self._picker._handle_drag_event(event)

    def dragMoveEvent(self, event):
        self._picker._handle_drag_event(event)

    def dragLeaveEvent(self, event):
        self._picker._set_drop_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self._picker._handle_drop_event(event)


class AppButton(QPushButton):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._sync_cursor()

    def setEnabled(self, enabled: bool):
        super().setEnabled(enabled)
        self._sync_cursor()

    def changeEvent(self, event):
        super().changeEvent(event)
        self._sync_cursor()

    def _sync_cursor(self):
        self.setCursor(Qt.PointingHandCursor if self.isEnabled() else Qt.ArrowCursor)


class PathPicker(QWidget):
    def __init__(
        self,
        title: str,
        subtitle: str,
        button_text: str = "Browse",
        parent=None,
        *,
        drop_kind: str = "folder",
        supported_extensions: set[str] | list[str] | tuple[str, ...] | None = None,
    ):
        super().__init__(parent)
        self.drop_kind = drop_kind
        self.supported_extensions = _normalize_extensions(supported_extensions)
        self.setAcceptDrops(True)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(8)

        self.title_label = make_label(title)
        self.title_label.setStyleSheet("font-weight: 700;")
        self.subtitle_label = make_label(subtitle, muted=True)
        self.layout.addWidget(self.title_label)
        self.layout.addWidget(self.subtitle_label)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        self.line_edit = DropPathLineEdit(self)
        self.line_edit.setReadOnly(True)
        self.line_edit.setPlaceholderText("Browse or drag here")
        self.line_edit.setMinimumHeight(40)
        self.button = make_button(button_text)
        self.button.setMinimumWidth(108)
        row.addWidget(self.line_edit, 1)
        row.addWidget(self.button)
        self.layout.addLayout(row)

    def set_path(self, path: str | Path):
        self.line_edit.setText(str(path))

    def path(self) -> str:
        return self.line_edit.text().strip()

    def set_drop_options(
        self,
        *,
        drop_kind: str | None = None,
        supported_extensions: set[str] | list[str] | tuple[str, ...] | None = None,
    ):
        if drop_kind is not None:
            self.drop_kind = drop_kind

        if supported_extensions is not None:
            self.supported_extensions = _normalize_extensions(supported_extensions)

    def dragEnterEvent(self, event):
        self._handle_drag_event(event)

    def dragMoveEvent(self, event):
        self._handle_drag_event(event)

    def dragLeaveEvent(self, event):
        self._set_drop_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self._handle_drop_event(event)

    def _handle_drag_event(self, event):
        path, _warning, _message = self._first_acceptable_drop(event.mimeData())

        if path is not None:
            self._set_drop_active(True)
            event.acceptProposedAction()
            return

        self._set_drop_active(False)

        if self._has_local_urls(event.mimeData()):
            event.acceptProposedAction()
            return

        event.ignore()

    def _handle_drop_event(self, event):
        self._set_drop_active(False)
        path, warning, message = self._first_acceptable_drop(event.mimeData())

        if path is None:
            self._show_drop_message(message or self._drop_hint())
            event.ignore()
            return

        self.set_path(path)
        event.acceptProposedAction()

        if warning:
            self._show_drop_message(warning)

    def _first_acceptable_drop(self, mime_data):
        paths = []
        local_count = 0

        if not mime_data.hasUrls():
            return None, "", self._drop_hint()

        for url in mime_data.urls():
            if not url.isLocalFile():
                continue

            local_count += 1
            local = Path(url.toLocalFile())

            if self._is_valid_drop_path(local):
                paths.append(local)

        if paths:
            warning = ""

            if self.drop_kind == "file" and local_count > 1:
                warning = f"Using first valid file: {paths[0].name}"
            elif self.drop_kind == "folder" and local_count > 1:
                warning = f"Using first folder: {paths[0].name}"

            return paths[0], warning, ""

        return None, "", self._drop_hint()

    def _has_local_urls(self, mime_data) -> bool:
        return mime_data.hasUrls() and any(url.isLocalFile() for url in mime_data.urls())

    def _is_valid_drop_path(self, path: Path) -> bool:
        if self.drop_kind == "folder":
            return path.is_dir()

        if self.drop_kind == "file":
            if not path.is_file():
                return False

            return not self.supported_extensions or path.suffix.lower() in self.supported_extensions

        return path.exists()

    def _drop_hint(self) -> str:
        if self.drop_kind == "folder":
            return "Drop a folder here."

        if self.supported_extensions:
            return "Drop a supported file here."

        return "Drop a file here."

    def _set_drop_active(self, active: bool):
        set_role(self.line_edit, dropActive=active)
        refresh_style(self.line_edit)

    def _show_drop_message(self, message: str):
        QToolTip.showText(QCursor.pos(), message, self.line_edit, self.line_edit.rect(), 3000)


class AppComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        popup = QListView(self)
        popup.setObjectName("ComboPopup")
        popup.setFrameShape(QFrame.NoFrame)
        popup.setUniformItemSizes(True)
        popup.setMouseTracking(True)
        popup.setEditTriggers(QAbstractItemView.NoEditTriggers)
        popup.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        popup.viewport().setObjectName("ComboPopupViewport")
        self.setView(popup)
        self._polish_popup_container(apply_window_flags=True)
        self.setMinimumHeight(40)
        self.setMinimumWidth(220)
        self._sync_cursor()

    def setEnabled(self, enabled: bool):
        super().setEnabled(enabled)
        self._sync_cursor()

    def changeEvent(self, event):
        super().changeEvent(event)
        self._sync_cursor()

    def _sync_cursor(self):
        self.setCursor(Qt.PointingHandCursor if self.isEnabled() else Qt.ArrowCursor)

    def showPopup(self):
        self._polish_popup_container(apply_window_flags=True)
        super().showPopup()
        self._polish_popup_container(apply_window_flags=False)
        self._place_popup_container()
        QTimer.singleShot(0, self._place_popup_container)
        QTimer.singleShot(10, self._place_popup_container)

    def _fill_popup_container(self):
        view = self.view()
        container = view.window()

        if container is not None and container.isVisible():
            view.setGeometry(container.rect())
            view.raise_()

    def _place_popup_container(self):
        view = self.view()
        container = view.window()

        if container is None or not container.isVisible():
            return

        screen = self.screen() or QGuiApplication.screenAt(self.mapToGlobal(QPoint(0, 0))) or QGuiApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else self.window().geometry()
        below = self.mapToGlobal(QPoint(0, self.height()))
        above = self.mapToGlobal(QPoint(0, 0))
        width = self.width()
        height = container.height()
        row_height = max(24, view.sizeHintForRow(0))
        min_height = min(height, max(48, row_height * min(max(1, self.count()), 3)))
        below_space = max(0, available.bottom() - below.y() + 1)
        above_space = max(0, above.y() - available.top())

        if below_space >= height or below_space >= above_space or below_space >= min_height:
            y = below.y()
            height = min(height, below_space) if below_space else height
        else:
            height = min(height, above_space) if above_space else height
            y = above.y() - height

        x = max(available.left(), min(below.x(), available.right() - width + 1))
        height = max(min_height, height)
        container.setGeometry(x, y, width, height)
        self._fill_popup_container()

    def _polish_popup_container(self, *, apply_window_flags: bool):
        view = self.view()
        view.setFrameShape(QFrame.NoFrame)
        view.setLineWidth(0)
        view.setMidLineWidth(0)
        view.setContentsMargins(0, 0, 0, 0)
        view.setViewportMargins(0, 0, 0, 0)
        view.viewport().setAutoFillBackground(False)
        view.viewport().setContentsMargins(0, 0, 0, 0)

        container = view.window()

        if container is not None:
            container.setObjectName("ComboPopupContainer")
            container.setAttribute(Qt.WA_StyledBackground, True)
            container.setAttribute(Qt.WA_TranslucentBackground, False)
            if apply_window_flags:
                container.setWindowFlags(
                    container.windowFlags()
                    | Qt.FramelessWindowHint
                    | Qt.NoDropShadowWindowHint
                )
            container.setContentsMargins(0, 0, 0, 0)

            if isinstance(container, QFrame):
                container.setFrameShape(QFrame.NoFrame)
                container.setLineWidth(0)
                container.setMidLineWidth(0)

            layout = container.layout()

            if layout is not None:
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(0)

            refresh_style(container)
            refresh_style(view)

    def wheelEvent(self, event):
        if self.view().isVisible():
            super().wheelEvent(event)
            return

        event.ignore()

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self.isEnabled():
            color = self.palette().color(QPalette.Text)
        else:
            color = self.palette().color(QPalette.Disabled, QPalette.Text)
        pen = QPen(color, 1.7)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)

        center_y = self.rect().center().y()
        center_x = self.rect().right() - 18
        size = 5
        painter.drawLine(QPointF(center_x - size, center_y - 2), QPointF(center_x, center_y + 4))
        painter.drawLine(QPointF(center_x, center_y + 4), QPointF(center_x + size, center_y - 2))


class AppCheckBox(QCheckBox):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._sync_cursor()

    def setEnabled(self, enabled: bool):
        super().setEnabled(enabled)
        self._sync_cursor()

    def changeEvent(self, event):
        super().changeEvent(event)
        self._sync_cursor()

    def _sync_cursor(self):
        self.setCursor(Qt.PointingHandCursor if self.isEnabled() else Qt.ArrowCursor)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.isChecked():
            return

        option = QStyleOptionButton()
        self.initStyleOption(option)
        indicator = self.style().subElementRect(QStyle.SE_CheckBoxIndicator, option, self)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor("#FFFFFF"), 2.2)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)

        x = indicator.left()
        y = indicator.top()
        w = indicator.width()
        h = indicator.height()
        painter.drawLine(QPointF(x + w * 0.26, y + h * 0.52), QPointF(x + w * 0.43, y + h * 0.69))
        painter.drawLine(QPointF(x + w * 0.43, y + h * 0.69), QPointF(x + w * 0.75, y + h * 0.32))


class SegmentedControl(QFrame):
    def __init__(self, options: list[tuple[str, str]], value: str, parent=None):
        super().__init__(parent)
        self.setObjectName("SegmentedControl")
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.setMaximumWidth(300)
        self._value = value
        self._callbacks = []
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        for index, (key, label) in enumerate(options):
            button = make_button(label, "segment", checkable=True)
            button.setMinimumWidth(122)
            button.setMinimumHeight(34)
            button.setChecked(key == value)
            self.group.addButton(button, index)
            button.clicked.connect(lambda checked=False, current=key: self.set_value(current))
            layout.addWidget(button)

    def on_changed(self, callback):
        self._callbacks.append(callback)

    def value(self) -> str:
        return self._value

    def set_value(self, value: str):
        if value == self._value:
            return
        self._value = value
        for callback in self._callbacks:
            callback(value)


class LogView(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setAcceptRichText(True)
        self.setMinimumHeight(170)
        self.setMaximumHeight(260)

    def append_line(self, text: str, tag: str = "", theme: Theme | None = None):
        color = "#E5E7EB"
        if theme is not None:
            color = {
                "ok": theme.success,
                "err": theme.danger,
                "info": theme.info,
                "dim": theme.fg_muted,
            }.get(tag, "#E5E7EB")

        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.insertText(f"{text}\n", fmt)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def append_lines(self, lines: list[tuple[str, str]], theme: Theme):
        if not lines:
            return
        self.setUpdatesEnabled(False)
        try:
            for text, tag in lines:
                self.append_line(text, tag, theme)
        finally:
            self.setUpdatesEnabled(True)
            self.ensureCursorVisible()


class AppDialog(QDialog):
    def __init__(self, parent, title: str, theme: Theme):
        super().__init__(parent)
        self.theme = theme
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(460)

        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(18, 18, 18, 18)
        self.outer.setSpacing(0)

        self.card = Card(title)
        self.outer.addWidget(self.card)

    def add_text(self, text: str):
        label = make_label(text, muted=True)
        label.setTextFormat(Qt.PlainText)
        self.card.body_layout.addWidget(label)
        return label

    def add_actions(self, buttons: list[QPushButton]):
        row = QHBoxLayout()
        row.setContentsMargins(0, 8, 0, 0)
        row.setSpacing(10)
        row.addStretch(1)
        for button in buttons:
            row.addWidget(button)
        self.card.body_layout.addLayout(row)


class MessageDialog(AppDialog):
    def __init__(self, parent, title: str, message: str, theme: Theme, kind: str = "info"):
        super().__init__(parent, title, theme)
        self.add_text(message)
        ok = make_button("OK", "primary" if kind != "error" else "")
        ok.clicked.connect(self.accept)
        self.add_actions([ok])


class ConfirmDialog(AppDialog):
    def __init__(self, parent, title: str, message: str, theme: Theme):
        super().__init__(parent, title, theme)
        self.add_text(message)
        cancel = make_button("Cancel")
        confirm = make_button("Continue", "primary")
        cancel.clicked.connect(self.reject)
        confirm.clicked.connect(self.accept)
        self.add_actions([cancel, confirm])


class SupportDialog(AppDialog):
    def __init__(self, parent, theme: Theme):
        QDialog.__init__(self, parent)
        self.theme = theme
        self.setObjectName("SupportOverlay")
        self.setWindowTitle(f"Support {APP_NAME}")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setWindowModality(Qt.WindowModal)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setModal(True)

        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(24, 24, 24, 24)
        self.outer.setSpacing(0)

        self.card = QFrame()
        self.card.setObjectName("ModalCard")
        self.card.setMinimumWidth(500)
        self.card.setMaximumWidth(560)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(28, 26, 28, 24)
        card_layout.setSpacing(18)

        title = make_label(f"\u2665 Support {APP_NAME}", role="modalTitle")
        card_layout.addWidget(title)

        message = make_label(
            "Thank you for using ZDBatcher.\n\n"
            "If this app saved you time, you can leave a small crypto donation.\n\n"
            "Crypto is currently the only available support method due to payment "
            "limitations in my country.\n\n"
            "Any support is appreciated.",
            muted=True,
        )
        message.setTextFormat(Qt.PlainText)
        card_layout.addWidget(message)

        close = make_button("Close")
        support = make_button("Support with Crypto", "primary")
        close.setMinimumWidth(108)
        support.setMinimumWidth(180)
        close.clicked.connect(self.reject)
        support.clicked.connect(self._open_support)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 4, 0, 0)
        actions.setSpacing(12)
        actions.addWidget(close)
        actions.addStretch(1)
        actions.addWidget(support)
        card_layout.addLayout(actions)

        self.outer.addWidget(self.card, 0, Qt.AlignCenter)

    def showEvent(self, event):
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.window().geometry())
        super().showEvent(event)

    def _open_support(self):
        webbrowser.open(SUPPORT_URL)


def show_message(parent, title: str, message: str, theme: Theme, kind: str = "info"):
    dialog = MessageDialog(parent, title, message, theme, kind)
    dialog.exec()


def ask_confirm(parent, title: str, message: str, theme: Theme) -> bool:
    dialog = ConfirmDialog(parent, title, message, theme)
    return dialog.exec() == QDialog.Accepted


def make_temp_output_path(extension: str) -> Path:
    extension = extension.lower().lstrip(".")
    handle, path = tempfile.mkstemp(prefix="zdbatcher_", suffix=f".{extension}")
    try:
        import os

        os.close(handle)
    except OSError:
        pass
    return Path(path)


def save_temp_output(parent, temp_path: Path, default_filename: str, theme: Theme, log_func) -> Path | None:
    temp_path = Path(temp_path)
    log_func("Choose where to save...", "info")

    save_path, _selected = QFileDialog.getSaveFileName(
        parent,
        "Save converted file",
        default_filename,
        f"{temp_path.suffix.upper().lstrip('.')} file (*{temp_path.suffix});;All files (*.*)",
    )

    if save_path:
        destination = Path(save_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(temp_path), str(destination))
        log_func("Saved to:", "ok")
        log_func(str(destination), "ok")
        return destination

    log_func("Save canceled.", "dim")
    delete_temp = ask_confirm(
        parent,
        "Save canceled",
        "Save canceled.\nDelete the temporary converted file?",
        theme,
    )

    if delete_temp:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        log_func("Temporary file deleted.", "dim")
    else:
        log_func("Temporary file kept:", "info")
        log_func(str(temp_path), "info")
        show_message(parent, "Temporary file kept", f"Temporary file kept:\n{temp_path}", theme)

    return None


def file_filter(name: str, extensions: set[str] | list[str]) -> str:
    parts = []
    for ext in sorted(extensions):
        clean = ext if ext.startswith(".") else f".{ext}"
        parts.append(f"*{clean}")
    return f"{html.escape(name)} ({' '.join(parts)})"
