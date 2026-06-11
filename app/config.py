# App identity
APP_NAME = "ZDBatcher"
APP_VERSION = "0.1.0"
SUPPORT_URL = "https://nowpayments.io/donation/ZDBatcher"

# Supported image inputs
SUPPORTED_INPUTS = {
    ".jpg", ".jpeg",
    ".png",
    ".webp",
    ".avif",
    ".svg",
    ".bmp",
    ".gif",
    ".tiff", ".tif",
    ".ico",
    ".tga",
    ".pcx",
    ".heic", ".heif",
}

# Output formats shown in the UI
BASE_OUTPUT_FORMATS = ["jpg", "png", "webp", "tiff", "bmp"]

# Formats that support quality/compression
LOSSY_FORMATS = {"jpg", "jpeg", "webp", "avif"}

# UI themes
THEME_MODE = "dark"

THEME_COLOR_KEYS = (
    "BG", "SURFACE", "SURFACE_2", "BORDER", "BORDER_DARK",
    "FG", "FG_DIM", "FG_MUTED",
    "ACCENT", "ACCENT_HVR", "ACCENT_SOFT", "ACCENT_FG",
    "CONTROL_HOVER", "CONTROL_DISABLED_BG",
    "ACCENT_DISABLED_BG", "ACCENT_DISABLED_FG",
    "TEXT_SELECT_BG", "TEXT_SELECT_FG",
    "TOOLTIP_BG", "TOOLTIP_FG",
    "LOG_BG", "LOG_FG", "LOG_OK", "LOG_ERR", "LOG_INFO", "LOG_DIM",
)

THEME_BACKGROUND_KEYS = (
    "BG", "SURFACE", "SURFACE_2", "BORDER", "BORDER_DARK",
    "ACCENT", "ACCENT_HVR", "ACCENT_SOFT",
    "CONTROL_HOVER", "CONTROL_DISABLED_BG",
    "ACCENT_DISABLED_BG", "TEXT_SELECT_BG", "TOOLTIP_BG", "LOG_BG",
)

THEME_FOREGROUND_KEYS = (
    "FG", "FG_DIM", "FG_MUTED",
    "ACCENT", "ACCENT_HVR", "ACCENT_FG", "ACCENT_DISABLED_FG",
    "TEXT_SELECT_FG",
    "LOG_FG", "LOG_OK", "LOG_ERR", "LOG_INFO", "LOG_DIM",
)

THEME_PALETTES = {
    "light": {
        "BG": "#EEF1F5",
        "SURFACE": "#FFFFFF",
        "SURFACE_2": "#F7F8FA",
        "BORDER": "#DDE2E8",
        "BORDER_DARK": "#C9D0DA",
        "FG": "#1D2430",
        "FG_DIM": "#6C7584",
        "FG_MUTED": "#99A2AE",
        "ACCENT": "#2563EB",
        "ACCENT_HVR": "#1D4ED8",
        "ACCENT_SOFT": "#EAF1FF",
        "ACCENT_FG": "#FFFFFF",
        "CONTROL_HOVER": "#E8ECF2",
        "CONTROL_DISABLED_BG": "#E5E7EB",
        "ACCENT_DISABLED_BG": "#AEB7C4",
        "ACCENT_DISABLED_FG": "#F1F5F9",
        "TEXT_SELECT_BG": "#DBEAFE",
        "TEXT_SELECT_FG": "#1D2430",
        "TOOLTIP_BG": "#0F172A",
        "TOOLTIP_FG": "#F8FAFC",
        "LOG_BG": "#111827",
        "LOG_FG": "#E5E7EB",
        "LOG_OK": "#86EFAC",
        "LOG_ERR": "#FCA5A5",
        "LOG_INFO": "#93C5FD",
        "LOG_DIM": "#9CA3AF",
    },
    "dark": {
        "BG": "#0F172A",
        "SURFACE": "#172033",
        "SURFACE_2": "#202B3F",
        "BORDER": "#2D3A4F",
        "BORDER_DARK": "#475569",
        "FG": "#F8FAFC",
        "FG_DIM": "#CBD5E1",
        "FG_MUTED": "#94A3B8",
        "ACCENT": "#60A5FA",
        "ACCENT_HVR": "#3B82F6",
        "ACCENT_SOFT": "#1E3A5F",
        "ACCENT_FG": "#08111F",
        "CONTROL_HOVER": "#2A3850",
        "CONTROL_DISABLED_BG": "#1B2434",
        "ACCENT_DISABLED_BG": "#334155",
        "ACCENT_DISABLED_FG": "#94A3B8",
        "TEXT_SELECT_BG": "#1D4ED8",
        "TEXT_SELECT_FG": "#F8FAFC",
        "TOOLTIP_BG": "#020617",
        "TOOLTIP_FG": "#F8FAFC",
        "LOG_BG": "#050B16",
        "LOG_FG": "#E5E7EB",
        "LOG_OK": "#86EFAC",
        "LOG_ERR": "#FCA5A5",
        "LOG_INFO": "#93C5FD",
        "LOG_DIM": "#94A3B8",
    },
}


def set_theme_mode(mode: str):
    if mode not in THEME_PALETTES:
        raise ValueError(f"Unknown theme mode: {mode}")

    global THEME_MODE
    THEME_MODE = mode

    for key, value in THEME_PALETTES[mode].items():
        globals()[key] = value


def get_theme_mode() -> str:
    return THEME_MODE


def get_theme_palette(mode: str | None = None):
    return dict(THEME_PALETTES[mode or THEME_MODE])


set_theme_mode(THEME_MODE)

FONT_UI = "Segoe UI"
FONT_MONO = "Consolas"
