"""Small reusable widgets for the chat view: icons, shimmer labels, pre boxes."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from PySide6.QtCore import QByteArray, QEvent, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from . import theme

_ICON_CACHE: Dict[Tuple[str, str, int, float, float], QPixmap] = {}


def svg_pixmap(
    body: str,
    color: str,
    size: int,
    device_ratio: float = 1.0,
    stroke_width: float = 1.8,
) -> QPixmap:
    """Render one of the theme SVG icon bodies at ``size`` px in ``color``."""
    key = (body, color, size, device_ratio, stroke_width)
    cached = _ICON_CACHE.get(key)
    if cached is not None:
        return cached
    renderer = QSvgRenderer(QByteArray(theme.svg_markup(body, color, stroke_width).encode("utf-8")))
    pixel = max(1, round(size * device_ratio))
    pixmap = QPixmap(pixel, pixel)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, pixel, pixel))
    painter.end()
    pixmap.setDevicePixelRatio(device_ratio)
    _ICON_CACHE[key] = pixmap
    return pixmap


class IconLabel(QLabel):
    """Fixed-size label showing a theme SVG icon."""

    def __init__(self, body: str, color: str, size: int = 16, box: int = 24, parent=None):
        super().__init__(parent)
        self._body = body
        self._color = color
        self._size = size
        self.setFixedSize(box, box)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._refresh()

    def set_color(self, color: str) -> None:
        if color != self._color:
            self._color = color
            self._refresh()

    def _refresh(self) -> None:
        ratio = self.devicePixelRatioF() if self.window() else 1.0
        self.setPixmap(svg_pixmap(self._body, self._color, self._size, ratio))


class ChevronLabel(IconLabel):
    """Chevron that rotates 90 degrees when the parent is expanded."""

    def __init__(self, parent=None):
        super().__init__(theme.ICON_CHEVRON, theme.ACTIVITY_ICON, 12, 16, parent)
        self._open = False

    def set_open(self, is_open: bool) -> None:
        self._open = is_open
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setOpacity(0.6)
        pixmap = self.pixmap()
        if pixmap is None or pixmap.isNull():
            return
        painter.translate(self.width() / 2, self.height() / 2)
        if self._open:
            painter.rotate(90)
        size = pixmap.deviceIndependentSize()
        painter.drawPixmap(QRectF(-size.width() / 2, -size.height() / 2, size.width(), size.height()).toRect(), pixmap)


class ShineLabel(QWidget):
    """Single-line label whose text can show a moving highlight sweep.

    Reproduces the ``.working-shine`` / ``.activity-title.shine`` effect: the
    base text is drawn in ``base_color`` and a bright band the width of about
    four and a half ems sweeps across it every 2.2 seconds while active.
    """

    _PERIOD_MS = 2200
    _TICK_MS = 33

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._text = text
        self._base_color = QColor(theme.MUTED)
        self._shine_color = QColor(theme.TEXT)
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(self._TICK_MS)
        self._timer.timeout.connect(self._advance)
        self._elide = False
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_text(self, text: str) -> None:
        if text != self._text:
            self._text = text
            self.updateGeometry()
            self.update()

    def text(self) -> str:
        return self._text

    def set_colors(self, base: str, shine: str) -> None:
        self._base_color = QColor(base)
        self._shine_color = QColor(shine)
        self.update()

    def set_elide(self, enabled: bool) -> None:
        self._elide = enabled
        if enabled:
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_shining(self, active: bool) -> None:
        if active and not self._timer.isActive():
            self._phase = 0.0
            self._timer.start()
        elif not active and self._timer.isActive():
            self._timer.stop()
        self.update()

    def _advance(self) -> None:
        self._phase = (self._phase + self._TICK_MS / self._PERIOD_MS) % 1.0
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        metrics = QFontMetrics(self.font())
        width = metrics.horizontalAdvance(self._text) + 2
        return QSize(width, metrics.height())

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        metrics = QFontMetrics(self.font())
        if self._elide:
            return QSize(metrics.horizontalAdvance("...") + 2, metrics.height())
        return self.sizeHint()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        metrics = QFontMetrics(self.font())
        text = self._text
        if self._elide:
            text = metrics.elidedText(text, Qt.TextElideMode.ElideRight, self.width())
        rect = self.rect()
        painter.setPen(self._base_color)
        painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
        if not self._timer.isActive():
            return
        band = 4.5 * metrics.averageCharWidth() * 2.0
        total = rect.width() + 2 * band
        x = -band + self._phase * total
        gradient = QLinearGradient(x, 0, x + band, 0)
        transparent = QColor(self._shine_color)
        transparent.setAlpha(0)
        mid = QColor(self._shine_color)
        mid.setAlpha(140)
        gradient.setColorAt(0.0, transparent)
        gradient.setColorAt(0.15, mid)
        gradient.setColorAt(0.5, self._shine_color)
        gradient.setColorAt(0.85, mid)
        gradient.setColorAt(1.0, transparent)
        painter.setPen(QPen(gradient, 0))
        painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)


class ElidedLabel(QLabel):
    """Single-line label that elides its text on the right."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._full_text = text
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(24)
        self._apply()

    def set_full_text(self, text: str) -> None:
        self._full_text = text
        self.setToolTip(text if text else "")
        self._apply()
        self.updateGeometry()

    def sizeHint(self) -> QSize:  # noqa: N802
        metrics = QFontMetrics(self.font())
        return QSize(metrics.horizontalAdvance(self._full_text) + 4, metrics.height())

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply()

    def _apply(self) -> None:
        metrics = QFontMetrics(self.font())
        super().setText(metrics.elidedText(self._full_text, Qt.TextElideMode.ElideRight, max(8, self.width())))


class PreBox(QPlainTextEdit):
    """Read-only monospace block that grows with its content up to a cap.

    Mirrors the ``pre`` in an activity body: wraps long lines, scrolls once
    it exceeds ``max_height`` px, and lets Ctrl+wheel bubble up for zoom.
    """

    def __init__(self, text: str = "", max_height: int = 320, font=None, parent=None):
        super().__init__(parent)
        self._max_height = max_height
        if font is not None:
            self.setFont(font)
        self.setReadOnly(True)
        self.setFrameShape(QPlainTextEdit.Shape.NoFrame)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            "QPlainTextEdit { background: transparent; border: none; padding: 0px; "
            f"color: {theme.TEXT}; selection-background-color: {theme.ACCENT}; }}"
        )
        self.document().documentLayout().documentSizeChanged.connect(self._fit)
        self.setPlainText(text)

    def set_max_height(self, max_height: int) -> None:
        self._max_height = max_height
        self._fit()

    def wheelEvent(self, event) -> None:  # noqa: N802
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            event.ignore()
            return
        bar = self.verticalScrollBar()
        if bar.maximum() == 0:
            event.ignore()
            return
        super().wheelEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit()

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() == QEvent.Type.FontChange:
            self._fit()

    def _fit(self, *_args) -> None:
        # QPlainTextDocumentLayout reports the document height in wrapped lines.
        lines = max(1.0, self.document().size().height())
        margin = self.document().documentMargin() * 2
        content = lines * self.fontMetrics().lineSpacing() + margin + 4
        target = int(min(self._max_height, content))
        if target != self.height():
            self.setFixedHeight(target)


class SegmentedToggle(QWidget):
    """Two-option segmented control matching the Skylyx ``.segmented`` group."""

    changed = Signal(str)

    def __init__(self, options: Tuple[Tuple[str, str], ...], parent=None):
        super().__init__(parent)
        self._buttons: Dict[str, QPushButton] = {}
        self._value: Optional[str] = None
        self.setObjectName("chat_segmented")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(3)
        for value, label in options:
            button = QPushButton(label)
            button.setObjectName("chat_segmented_button")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.clicked.connect(lambda _checked=False, v=value: self.set_value(v, emit=True))
            layout.addWidget(button)
            self._buttons[value] = button
        self.set_text_scale(1.0)

    def set_text_scale(self, scale: float) -> None:
        font_px = max(8, round(11 * scale))
        self.setStyleSheet(
            f"QWidget#chat_segmented {{ border: 1px solid {theme.LINE}; border-radius: 7px; "
            f"background: {theme.SEGMENTED_BG}; }}"
            f"QPushButton#chat_segmented_button {{ border: none; border-radius: 5px; background: transparent; "
            f"padding: 5px 10px; font-size: {font_px}px; color: {theme.SEGMENTED_TEXT}; text-align: center; }}"
            f"QPushButton#chat_segmented_button:checked {{ background: {theme.SEGMENTED_ACTIVE_BG}; "
            f"color: {theme.SEGMENTED_ACTIVE_TEXT}; }}"
        )
        for button in self._buttons.values():
            button.setFont(theme.ui_font(11, scale=scale))

    def value(self) -> Optional[str]:
        return self._value

    def set_value(self, value: str, emit: bool = False) -> None:
        for key, button in self._buttons.items():
            button.blockSignals(True)
            button.setChecked(key == value)
            button.blockSignals(False)
        changed = value != self._value
        self._value = value
        if emit and changed:
            self.changed.emit(value)
