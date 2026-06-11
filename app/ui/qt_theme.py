from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    name: str
    bg: str
    sidebar: str
    surface: str
    surface_2: str
    surface_3: str
    border: str
    border_soft: str
    fg: str
    fg_dim: str
    fg_muted: str
    accent: str
    accent_hover: str
    accent_soft: str
    accent_fg: str
    danger: str
    success: str
    info: str
    log_bg: str
    shadow: str
    modal_overlay: str
    disabled_bg: str
    disabled_border: str
    disabled_fg: str
    disabled_checked: str


THEMES = {
    "dark": Theme(
        name="dark",
        bg="#0F1117",
        sidebar="#141821",
        surface="#191E28",
        surface_2="#212834",
        surface_3="#2A3341",
        border="#3A4658",
        border_soft="#2B3443",
        fg="#F4F7FA",
        fg_dim="#C2CBD7",
        fg_muted="#8793A3",
        accent="#6EA8FE",
        accent_hover="#88B9FF",
        accent_soft="#1E344F",
        accent_fg="#08111E",
        danger="#FF8585",
        success="#83D897",
        info="#94BEFF",
        log_bg="#0B0E14",
        shadow="#050607",
        modal_overlay="rgba(4, 7, 12, 168)",
        disabled_bg="#171C25",
        disabled_border="#202835",
        disabled_fg="#596475",
        disabled_checked="#334258",
    ),
    "light": Theme(
        name="light",
        bg="#F3F6FA",
        sidebar="#E8EDF4",
        surface="#FFFFFF",
        surface_2="#F7F9FC",
        surface_3="#EEF3F8",
        border="#CDD7E4",
        border_soft="#E3EAF2",
        fg="#17202C",
        fg_dim="#5B6675",
        fg_muted="#8995A5",
        accent="#2563EB",
        accent_hover="#1D4ED8",
        accent_soft="#E6F0FF",
        accent_fg="#FFFFFF",
        danger="#C24141",
        success="#18794E",
        info="#2563EB",
        log_bg="#111827",
        shadow="#C8D0DC",
        modal_overlay="rgba(15, 23, 42, 92)",
        disabled_bg="#E9EEF5",
        disabled_border="#D8E0EA",
        disabled_fg="#A5AFBD",
        disabled_checked="#B8C5D6",
    ),
}


def get_theme(mode: str) -> Theme:
    return THEMES.get(mode, THEMES["dark"])


def stylesheet(theme: Theme) -> str:
    return f"""
    * {{
        font-family: "Segoe UI";
        font-size: 10pt;
        outline: none;
    }}

    QMainWindow,
    QWidget#AppRoot {{
        background: {theme.bg};
        color: {theme.fg};
    }}

    QWidget#Sidebar {{
        background: {theme.sidebar};
        border-right: 1px solid {theme.border_soft};
    }}

    QWidget#PageHost,
    QWidget#PageContent,
    QWidget#ScrollContent,
    QWidget#ContentColumn,
    QWidget#PageHeader {{
        background: {theme.bg};
    }}

    QWidget#CardBody {{
        background: transparent;
    }}

    QWidget#AppHeader {{
        background: {theme.bg};
        border-bottom: 1px solid {theme.border_soft};
    }}

    QLabel {{
        color: {theme.fg};
        background: transparent;
    }}

    QLabel[muted="true"] {{
        color: {theme.fg_dim};
    }}

    QLabel[eyebrow="true"] {{
        color: {theme.accent};
        font-size: 8pt;
        font-weight: 700;
        letter-spacing: 0px;
    }}

    QLabel[pageTitle="true"] {{
        color: {theme.fg};
        font-size: 22pt;
        font-weight: 700;
    }}

    QLabel[cardTitle="true"] {{
        color: {theme.fg};
        font-size: 12pt;
        font-weight: 700;
    }}

    QLabel[modalTitle="true"] {{
        color: {theme.fg};
        font-size: 17pt;
        font-weight: 800;
    }}

    QLabel[statusTitle="true"] {{
        font-size: 13pt;
        font-weight: 700;
    }}

    QLabel[pill="true"] {{
        color: {theme.accent};
        background: {theme.accent_soft};
        border-radius: 12px;
        padding: 4px 10px;
        font-weight: 700;
    }}

    QLabel[sidebarFooter="true"] {{
        color: {theme.fg_muted};
        font-size: 9pt;
    }}

    QFrame#Card {{
        background: {theme.surface};
        border: 1px solid {theme.border_soft};
        border-radius: 10px;
    }}

    QFrame#ActionPanel {{
        background: {theme.surface};
        border: 1px solid {theme.border_soft};
        border-radius: 10px;
    }}

    QFrame#ModalCard {{
        background: {theme.surface};
        border: 1px solid {theme.border};
        border-radius: 12px;
    }}

    QFrame#Divider {{
        background: {theme.border_soft};
        min-height: 1px;
        max-height: 1px;
    }}

    QPushButton {{
        background: {theme.surface_2};
        color: {theme.fg};
        border: 1px solid {theme.border_soft};
        border-radius: 8px;
        padding: 9px 14px;
        font-weight: 600;
    }}

    QPushButton:hover {{
        background: {theme.surface_3};
        border-color: {theme.border};
    }}

    QPushButton:pressed {{
        background: {theme.border};
    }}

    QPushButton:disabled {{
        background: {theme.disabled_bg};
        color: {theme.disabled_fg};
        border-color: {theme.disabled_border};
    }}

    QPushButton:disabled:hover,
    QPushButton:disabled:pressed {{
        background: {theme.disabled_bg};
        color: {theme.disabled_fg};
        border-color: {theme.disabled_border};
    }}

    QPushButton[variant="primary"] {{
        background: {theme.accent};
        color: {theme.accent_fg};
        border-color: {theme.accent};
        font-weight: 700;
    }}

    QPushButton[variant="primary"]:hover {{
        background: {theme.accent_hover};
        border-color: {theme.accent_hover};
    }}

    QPushButton[variant="primary"]:disabled,
    QPushButton[variant="primary"]:disabled:hover,
    QPushButton[variant="primary"]:disabled:pressed {{
        background: {theme.disabled_bg};
        color: {theme.disabled_fg};
        border-color: {theme.disabled_border};
    }}

    QPushButton[variant="ghost"] {{
        background: transparent;
        border-color: transparent;
        color: {theme.fg_dim};
        text-align: left;
        padding: 10px 12px;
    }}

    QPushButton[variant="ghost"]:hover {{
        background: {theme.surface_2};
        color: {theme.fg};
    }}

    QPushButton[variant="ghost"]:disabled,
    QPushButton[variant="ghost"]:disabled:hover,
    QPushButton[variant="ghost"]:disabled:pressed {{
        background: transparent;
        color: {theme.disabled_fg};
        border-color: transparent;
    }}

    QPushButton[variant="nav"] {{
        background: transparent;
        border: 1px solid transparent;
        color: {theme.fg_dim};
        text-align: left;
        border-radius: 8px;
        padding: 10px 12px;
        font-weight: 600;
    }}

    QPushButton[variant="nav"]:hover {{
        background: {theme.surface_2};
        color: {theme.fg};
    }}

    QPushButton[variant="nav"]:checked {{
        background: {theme.accent_soft};
        color: {theme.accent};
        border-color: {theme.border};
    }}

    QPushButton[variant="nav"]:disabled,
    QPushButton[variant="nav"]:disabled:hover,
    QPushButton[variant="nav"]:disabled:pressed {{
        background: transparent;
        color: {theme.disabled_fg};
        border-color: transparent;
    }}

    QPushButton[variant="support"] {{
        background: {theme.surface_2};
        color: {theme.accent};
        border-color: {theme.border_soft};
        font-weight: 700;
    }}

    QPushButton[variant="support"]:hover {{
        background: {theme.accent_soft};
        border-color: {theme.border};
    }}

    QPushButton[variant="support"]:disabled,
    QPushButton[variant="support"]:disabled:hover,
    QPushButton[variant="support"]:disabled:pressed {{
        background: {theme.disabled_bg};
        color: {theme.disabled_fg};
        border-color: {theme.disabled_border};
    }}

    QPushButton[variant="segment"] {{
        background: transparent;
        color: {theme.fg_dim};
        border: 1px solid transparent;
        border-radius: 7px;
        padding: 7px 14px;
    }}

    QPushButton[variant="segment"]:hover {{
        background: {theme.surface_3};
        color: {theme.fg};
        border-color: transparent;
    }}

    QPushButton[variant="segment"]:checked {{
        background: {theme.accent};
        color: {theme.accent_fg};
        border-color: {theme.accent};
    }}

    QPushButton[variant="segment"]:disabled,
    QPushButton[variant="segment"]:disabled:hover,
    QPushButton[variant="segment"]:disabled:pressed {{
        background: transparent;
        color: {theme.disabled_fg};
        border-color: transparent;
    }}

    QPushButton[variant="segment"]:checked:disabled {{
        background: {theme.disabled_checked};
        color: {theme.disabled_fg};
        border-color: {theme.disabled_border};
    }}

    QFrame#SegmentedControl {{
        background: {theme.surface_2};
        border: 1px solid {theme.border_soft};
        border-radius: 10px;
    }}

    QLineEdit,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox {{
        background: {theme.surface_2};
        color: {theme.fg};
        border: 1px solid {theme.border_soft};
        border-radius: 8px;
        padding: 8px 11px;
        min-height: 20px;
        selection-background-color: {theme.accent};
        selection-color: {theme.accent_fg};
    }}

    QComboBox {{
        padding-right: 38px;
    }}

    QLineEdit:hover,
    QComboBox:hover,
    QSpinBox:hover,
    QDoubleSpinBox:hover {{
        background: {theme.surface_3};
        border-color: {theme.border};
    }}

    QLineEdit:disabled,
    QComboBox:disabled,
    QSpinBox:disabled,
    QDoubleSpinBox:disabled {{
        background: {theme.disabled_bg};
        color: {theme.disabled_fg};
        border-color: {theme.disabled_border};
        selection-background-color: {theme.disabled_checked};
        selection-color: {theme.disabled_fg};
    }}

    QLineEdit:disabled:hover,
    QComboBox:disabled:hover,
    QSpinBox:disabled:hover,
    QDoubleSpinBox:disabled:hover,
    QLineEdit:disabled:focus,
    QComboBox:disabled:focus,
    QSpinBox:disabled:focus,
    QDoubleSpinBox:disabled:focus {{
        background: {theme.disabled_bg};
        color: {theme.disabled_fg};
        border-color: {theme.disabled_border};
    }}

    QLineEdit:focus,
    QComboBox:focus,
    QSpinBox:focus,
    QDoubleSpinBox:focus {{
        border-color: {theme.accent};
    }}

    QLineEdit[dropActive="true"] {{
        background: {theme.accent_soft};
        border-color: {theme.accent};
        color: {theme.fg};
    }}

    QLineEdit:read-only {{
        color: {theme.fg_dim};
    }}

    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 34px;
        border-left: 1px solid {theme.border_soft};
        border-top-right-radius: 8px;
        border-bottom-right-radius: 8px;
        background: transparent;
    }}

    QComboBox::drop-down:disabled {{
        border-left: 1px solid {theme.disabled_border};
    }}

    QComboBox::down-arrow {{
        width: 0px;
        height: 0px;
    }}

    QFrame#ComboPopupContainer {{
        background: {theme.surface};
        border: 0px;
        margin: 0px;
        padding: 0px;
    }}

    QComboBox QAbstractItemView {{
        background: {theme.surface};
        color: {theme.fg};
        border: 1px solid {theme.border};
        border-radius: 6px;
        padding: 2px;
        margin: 0px;
        outline: 0px;
        selection-background-color: {theme.accent_soft};
        selection-color: {theme.fg};
        show-decoration-selected: 1;
    }}

    QComboBox QAbstractItemView QWidget#ComboPopupViewport {{
        background: {theme.surface};
    }}

    QComboBox QAbstractItemView::item {{
        background: transparent;
        color: {theme.fg};
        min-height: 24px;
        padding: 4px 8px;
        border: 0px;
        border-radius: 4px;
    }}

    QComboBox QAbstractItemView::item:hover {{
        background: {theme.surface_2};
        color: {theme.fg};
    }}

    QComboBox QAbstractItemView::item:selected,
    QComboBox QAbstractItemView::item:selected:active,
    QComboBox QAbstractItemView::item:selected:!active {{
        background: {theme.accent_soft};
        color: {theme.fg};
    }}

    QCheckBox {{
        color: {theme.fg};
        spacing: 9px;
        padding: 2px 0px;
    }}

    QCheckBox:disabled {{
        color: {theme.disabled_fg};
    }}

    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border-radius: 5px;
        border: 1px solid {theme.border};
        background: {theme.surface_2};
    }}

    QCheckBox::indicator:hover {{
        border-color: {theme.accent};
        background: {theme.surface_3};
    }}

    QCheckBox::indicator:checked {{
        background: {theme.accent};
        border-color: {theme.accent};
    }}

    QCheckBox::indicator:disabled,
    QCheckBox::indicator:disabled:hover {{
        background: {theme.disabled_bg};
        border-color: {theme.disabled_border};
    }}

    QCheckBox::indicator:checked:disabled,
    QCheckBox::indicator:checked:disabled:hover {{
        background: {theme.disabled_checked};
        border-color: {theme.disabled_border};
    }}

    QRadioButton {{
        color: {theme.fg};
        spacing: 8px;
    }}

    QRadioButton:disabled {{
        color: {theme.disabled_fg};
    }}

    QRadioButton::indicator {{
        width: 17px;
        height: 17px;
        border-radius: 9px;
        border: 1px solid {theme.border};
        background: {theme.surface_2};
    }}

    QRadioButton::indicator:checked {{
        background: {theme.accent};
        border: 4px solid {theme.surface_2};
    }}

    QRadioButton::indicator:disabled,
    QRadioButton::indicator:disabled:hover {{
        background: {theme.disabled_bg};
        border: 1px solid {theme.disabled_border};
    }}

    QRadioButton::indicator:checked:disabled {{
        background: {theme.disabled_checked};
        border: 4px solid {theme.disabled_bg};
    }}

    QProgressBar {{
        background: {theme.surface_2};
        border: 1px solid {theme.border_soft};
        border-radius: 7px;
        height: 12px;
        text-align: center;
        color: transparent;
    }}

    QProgressBar::chunk {{
        background: {theme.accent};
        border-radius: 6px;
    }}

    QTextEdit,
    QPlainTextEdit {{
        background: {theme.log_bg};
        color: #E5E7EB;
        border: 1px solid {theme.border_soft};
        border-radius: 10px;
        padding: 10px;
        selection-background-color: {theme.accent};
        selection-color: {theme.accent_fg};
        font-family: "Consolas";
        font-size: 9.5pt;
    }}

    QScrollArea {{
        background: transparent;
        border: 0px;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 12px;
        margin: 3px;
    }}

    QScrollBar::handle:vertical {{
        background: {theme.border};
        border-radius: 5px;
        min-height: 42px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {theme.fg_muted};
    }}

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        background: transparent;
        border: 0px;
        height: 0px;
    }}

    QScrollBar:horizontal {{
        background: transparent;
        height: 12px;
        margin: 3px;
    }}

    QScrollBar::handle:horizontal {{
        background: {theme.border};
        border-radius: 5px;
        min-width: 42px;
    }}

    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal,
    QScrollBar::add-page:horizontal,
    QScrollBar::sub-page:horizontal {{
        background: transparent;
        border: 0px;
        width: 0px;
    }}

    QSplitter::handle {{
        background: transparent;
    }}

    QDialog {{
        background: {theme.bg};
        color: {theme.fg};
    }}

    QDialog#SupportOverlay {{
        background: {theme.modal_overlay};
    }}
    """
