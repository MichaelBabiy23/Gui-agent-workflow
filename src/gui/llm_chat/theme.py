"""Design tokens for the LLM chat view.

The values mirror the Skylyx Hub code-tab chat (dark theme): its CSS custom
properties are resolved here into concrete colors so the native Qt widgets
render the same palette, type sizes, and icons.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont

# --bg / --text / --accent / --glare / --shade
BG = "#181c22"
TEXT = "#cccfd7"
ACCENT = "#22d3ee"
GLARE = "#ffffff"
SHADE = "#000000"

# Derived color-mix() results.
MUTED = "#8d9098"              # mix(bg 35%, text)
LINE = "#2c3036"               # mix(bg 89%, text)
LINE_SOFT = "#262a30"          # line at 60% over bg
SOFT = "#1d2127"               # mix(bg 97%, text)
DARK = "#0d0f12"               # mix(bg 53%, shade)
BUBBLE_BG = "#24272d"          # glare 5% over bg
BUBBLE_BORDER = "#21252b"      # glare 4% over bg
ROW_HOVER = "#21252b"          # glare 6% over bg (rounded)
ACTIVITY_BODY_BG = "#1f2329"   # glare 3% over bg
ACTIVITY_ICON = "#7b7e86"      # mix(bg 45%, text)
ACTIVITY_TITLE = "#9699a1"     # mix(bg 30%, text)
CRUMB_SEP = "#696c73"          # mix(bg 55%, text)
EMPTY_TEXT = "#7b7e86"
DIFF_ADD = "#69bd8d"
DIFF_REMOVE = "#e8838b"
LIVE_BG = "#19363f"            # accent 14% over bg
LIVE_TEXT = "#64e0f3"          # mix(accent 70%, glare)
SEGMENTED_BG = "#1c2026"       # mix(bg 98%, text)
SEGMENTED_TEXT = "#888b92"     # mix(bg 38%, text)
SEGMENTED_ACTIVE_BG = "#23272d"
SEGMENTED_ACTIVE_TEXT = "#b3b6be"
HEADING_TEXT = "#e1e2e8"
LINK = ACCENT

UI_FAMILIES = ["Manrope", "Segoe UI", "Arial"]
CODE_FAMILIES = ["JetBrains Mono", "Consolas", "Courier New"]

COLUMN_MAX_WIDTH = 768
COLUMN_PADDING = (20, 20, 20, 24)   # left, top, right, bottom
BUBBLE_MAX_FRACTION = 0.8
HEADER_HEIGHT = 52


_WEIGHTS = {
    400: QFont.Weight.Normal,
    500: QFont.Weight.Medium,
    600: QFont.Weight.DemiBold,
    700: QFont.Weight.Bold,
}


def ui_font(size_px: float, weight=QFont.Weight.Normal, scale: float = 1.0) -> QFont:
    """Build the UI font; ``weight`` accepts a CSS number (400/500/600/700) or a QFont.Weight."""
    font = QFont()
    font.setFamilies(UI_FAMILIES)
    font.setPixelSize(max(8, round(size_px * scale)))
    if isinstance(weight, int) and not isinstance(weight, QFont.Weight):
        weight = _WEIGHTS.get(weight, QFont.Weight.Normal)
    font.setWeight(weight)
    return font


def code_font(size_px: float, scale: float = 1.0) -> QFont:
    font = QFont()
    font.setFamilies(CODE_FAMILIES)
    font.setPixelSize(max(8, round(size_px * scale)))
    font.setStyleHint(QFont.StyleHint.Monospace)
    return font


def qcolor(value: str, alpha: float = 1.0) -> QColor:
    color = QColor(value)
    if alpha < 1.0:
        color.setAlphaF(alpha)
    return color


# SVG icons copied from the Skylyx chat components (24x24 stroke icons).
_SVG_HEAD = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round">'
)

ICON_COMMAND = '<path d="m4 17 6-5-6-5M12 19h8"/>'
ICON_EDIT = '<path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>'
ICON_READ = '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>'
ICON_THINKING = (
    '<path d="M9.5 3a3.5 3.5 0 0 0-3.4 4.3A3.5 3.5 0 0 0 4 12a3.5 3.5 0 0 0 2 6.3A3.5 3.5 0 0 0 12 20V7a3.5 3.5 0 0 0-2.5-4Z"/>'
    '<path d="M14.5 3a3.5 3.5 0 0 1 3.4 4.3A3.5 3.5 0 0 1 20 12a3.5 3.5 0 0 1-2 6.3A3.5 3.5 0 0 1 12 20V7a3.5 3.5 0 0 1 2.5-4Z"/>'
)
ICON_SEARCH = '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>'
ICON_DIAGNOSTIC = '<circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/>'
ICON_TOOL = (
    '<path d="M14.7 6.3a4 4 0 0 0 5 5L22 9l-3-3-2.3 2.3M3 21l8.5-8.5"/>'
    '<path d="m9.3 9.3-6.3 6.3a1.4 1.4 0 0 0 0 2l1.4 1.4a1.4 1.4 0 0 0 2 0l6.3-6.3"/>'
)
ICON_CHEVRON = '<path d="m9 6 6 6-6 6"/>'
ICON_FOLDER = '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"/>'
ICON_SETTINGS = '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>'
ICON_CHAT = '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M9 20V9"/>'


def svg_markup(body: str, color: str, stroke_width: float = 1.8) -> str:
    return _SVG_HEAD.format(color=color, width=stroke_width) + body + "</svg>"
