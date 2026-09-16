"""Chat transcript view and header for the LLM node Output page."""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .activity_widget import ActivityWidget
from .common_widgets import ElidedLabel, IconLabel, SegmentedToggle
from .message_widgets import AssistantWidget, EmptyStateWidget, UserTurnWidget
from .transcript import (
    CHANGE_APPEND,
    CHANGE_RESET,
    CHANGE_UPDATE,
    KIND_ASSISTANT,
    KIND_USER,
    ChatItem,
    ChatTranscript,
)

VIEW_SETTINGS = "settings"
VIEW_OUTPUT = "output"
EMPTY_TEXT = "Run this node to start the conversation."
FOLLOW_THRESHOLD_PX = 80


class LivePill(QFrame):
    """The ``Working`` pill with a pulsing dot shown while a turn runs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chat_live")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(6)
        self._dot = QLabel()
        self._dot.setFixedSize(6, 6)
        layout.addWidget(self._dot)
        self._label = QLabel("Working")
        layout.addWidget(self._label)
        self._pulse = QTimer(self)
        self._pulse.setInterval(40)
        self._pulse.timeout.connect(self._tick)
        self._phase = 0.0
        self.set_text_scale(1.0)

    def set_text_scale(self, scale: float) -> None:
        self.setFixedHeight(max(24, round(24 * scale)))
        self._label.setFont(theme.ui_font(11.5, 500, scale))
        self.setStyleSheet(
            f"QFrame#chat_live {{ background: {theme.LIVE_BG}; border-radius: {self.height() // 2}px; border: none; }}"
            f"QLabel {{ color: {theme.LIVE_TEXT}; background: transparent; }}"
        )
        self._paint_dot(1.0)

    def _paint_dot(self, opacity: float) -> None:
        alpha = int(255 * opacity)
        self._dot.setStyleSheet(
            f"background: rgba(100, 224, 243, {alpha}); border-radius: 3px;"
        )

    def _tick(self) -> None:
        self._phase = (self._phase + 40 / 1200) % 1.0
        # Mirrors composer-pulse: opacity dips to 0.35 at the midpoint.
        distance = abs(self._phase - 0.5) * 2
        self._paint_dot(0.35 + 0.65 * distance)

    def showEvent(self, event) -> None:  # noqa: N802
        self._pulse.start()
        super().showEvent(event)

    def hideEvent(self, event) -> None:  # noqa: N802
        self._pulse.stop()
        super().hideEvent(event)


class ChatHeader(QFrame):
    """52 px header: crumb (session) / title (node), live pill, view toggle."""

    view_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chat_header")
        self.setFixedHeight(theme.HEADER_HEIGHT)
        self.setStyleSheet(
            f"QFrame#chat_header {{ background: {theme.BG}; border: none; border-bottom: 1px solid {theme.LINE}; }}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 16, 0)
        layout.setSpacing(12)

        crumbs = QHBoxLayout()
        crumbs.setContentsMargins(0, 0, 0, 0)
        crumbs.setSpacing(10)
        crumb = QHBoxLayout()
        crumb.setContentsMargins(6, 3, 6, 3)
        crumb.setSpacing(6)
        self._crumb_icon = IconLabel(theme.ICON_FOLDER, theme.MUTED, 15, 15)
        crumb.addWidget(self._crumb_icon)
        self._crumb_label = ElidedLabel("")
        self._crumb_label.setMaximumWidth(220)
        self._crumb_label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self._crumb_label.setStyleSheet(f"color: {theme.MUTED};")
        crumb.addWidget(self._crumb_label)
        crumbs.addLayout(crumb)
        self._sep = QLabel("/")
        self._sep.setStyleSheet(f"color: {theme.CRUMB_SEP};")
        crumbs.addWidget(self._sep)
        self._title = ElidedLabel("")
        self._title.setStyleSheet(f"color: {theme.TEXT};")
        crumbs.addWidget(self._title, stretch=1)
        layout.addLayout(crumbs, stretch=1)

        self._live = LivePill()
        self._live.setVisible(False)
        layout.addWidget(self._live)

        self._toggle = SegmentedToggle(((VIEW_SETTINGS, "Settings"), (VIEW_OUTPUT, "Output")))
        self._toggle.set_value(VIEW_SETTINGS)
        self._toggle.changed.connect(self.view_changed)
        layout.addWidget(self._toggle)
        self.set_text_scale(1.0)

    def set_text_scale(self, scale: float) -> None:
        self.setFixedHeight(max(40, round(theme.HEADER_HEIGHT * scale)))
        self._crumb_label.setFont(theme.ui_font(14, 500, scale))
        self._crumb_label.set_full_text(self._crumb_label._full_text)
        self._sep.setFont(theme.ui_font(14, scale=scale))
        self._title.setFont(theme.ui_font(14, 500, scale))
        self._title.set_full_text(self._title._full_text)
        self._live.set_text_scale(scale)
        self._toggle.set_text_scale(scale)

    def set_crumb(self, text: str) -> None:
        self._crumb_label.set_full_text(text)

    def set_title(self, text: str) -> None:
        self._title.set_full_text(text)

    def set_busy(self, busy: bool) -> None:
        self._live.setVisible(busy)

    def view(self) -> str:
        return self._toggle.value() or VIEW_SETTINGS

    def set_view(self, view: str) -> None:
        self._toggle.set_value(view)


class ChatView(QWidget):
    """Scrolling chat column bound to one ``ChatTranscript``."""

    turn_started = Signal()
    busy_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._transcript: Optional[ChatTranscript] = None
        self._widgets: List[Optional[QWidget]] = []
        self._scale = 1.0
        self._follow = True
        self._show_sender = False
        self._rebuilding = False
        self._empty: Optional[EmptyStateWidget] = None
        self.setObjectName("chat_view")
        self.setStyleSheet(f"QWidget#chat_view {{ background: {theme.BG}; }}")
        self.setAutoFillBackground(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("chat_scroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            f"QScrollArea#chat_scroll {{ background: {theme.BG}; border: none; }}"
            f"QScrollArea#chat_scroll > QWidget > QWidget {{ background: {theme.BG}; }}"
        )
        self._scroll.viewport().installEventFilter(self)
        layout.addWidget(self._scroll)

        outer = QWidget()
        outer.setObjectName("chat_outer")
        outer_layout = QHBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        outer_layout.addStretch(1)
        self._column = QWidget()
        self._column.setObjectName("chat_column")
        self._column.setMaximumWidth(theme.COLUMN_MAX_WIDTH)
        self._column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        left, top, right, bottom = theme.COLUMN_PADDING
        self._column_layout = QVBoxLayout(self._column)
        self._column_layout.setContentsMargins(left, top, right, bottom)
        self._column_layout.setSpacing(0)
        self._column_layout.addStretch(1)
        outer_layout.addWidget(self._column, stretch=1000)
        outer_layout.addStretch(1)
        self._scroll.setWidget(outer)

        self._jump = QPushButton("↓ Latest", self)
        self._jump.setObjectName("jump_latest")
        self._jump.setCursor(Qt.CursorShape.PointingHandCursor)
        self._jump.setVisible(False)
        self._jump.clicked.connect(self._jump_to_latest)

        bar = self._scroll.verticalScrollBar()
        bar.valueChanged.connect(self._on_scrolled)
        bar.rangeChanged.connect(self._on_range_changed)

        self._ticker = QTimer(self)
        self._ticker.setInterval(1000)
        self._ticker.timeout.connect(self._tick)
        self.set_text_scale(1.0)
        self._rebuild()

    # ------------------------------------------------------------------
    # Binding
    # ------------------------------------------------------------------

    def set_transcript(self, transcript: Optional[ChatTranscript], show_sender: bool = False) -> None:
        if self._transcript is not None:
            self._transcript.remove_listener(self._on_change)
        self._transcript = transcript
        self._show_sender = show_sender
        if transcript is not None:
            transcript.add_listener(self._on_change)
        self._follow = True
        self._rebuild()
        self._sync_ticker()
        QTimer.singleShot(0, self._jump_to_latest)

    def transcript(self) -> Optional[ChatTranscript]:
        return self._transcript

    def set_text_scale(self, scale: float) -> None:
        self._scale = scale
        self._jump.setFont(theme.ui_font(12, scale=scale))
        self._jump.setStyleSheet(
            f"QPushButton#jump_latest {{ background: {theme.BUBBLE_BG}; color: {theme.TEXT}; "
            f"border: 1px solid {theme.LINE}; border-radius: 999px; padding: 6px 12px; }}"
            f"QPushButton#jump_latest:hover {{ background: {theme.ROW_HOVER}; }}"
        )
        self._jump.adjustSize()
        self._rebuild()

    # ------------------------------------------------------------------
    # Transcript changes
    # ------------------------------------------------------------------

    def _on_change(self, change: str, index: int) -> None:
        if self._transcript is None:
            return
        if change == CHANGE_RESET:
            self._rebuild()
        elif change == CHANGE_APPEND:
            self._append_widget(index)
        elif change == CHANGE_UPDATE and 0 <= index < len(self._widgets):
            widget = self._widgets[index]
            if widget is not None and hasattr(widget, "refresh"):
                widget.refresh(self._transcript.items[index])
        self._sync_ticker()
        if self._follow:
            QTimer.singleShot(0, self._jump_to_latest)

    @staticmethod
    def _discard(widget: QWidget) -> None:
        widget.hide()
        widget.setParent(None)
        widget.deleteLater()

    def _clear_column(self) -> None:
        while self._column_layout.count() > 1:
            child = self._column_layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                self._discard(widget)
        self._widgets = []
        self._empty = None

    def _rebuild(self) -> None:
        self._clear_column()
        items = self._transcript.items if self._transcript is not None else []
        if not items:
            self._empty = EmptyStateWidget(EMPTY_TEXT, self._scale)
            self._column_layout.insertWidget(0, self._empty)
            return
        self._rebuilding = True
        try:
            for index in range(len(items)):
                self._append_widget(index)
        finally:
            self._rebuilding = False

    def _append_widget(self, index: int) -> None:
        if self._transcript is None or index >= len(self._transcript.items):
            return
        if self._empty is not None:
            self._column_layout.removeWidget(self._empty)
            self._discard(self._empty)
            self._empty = None
        while len(self._widgets) < index:
            self._widgets.append(None)
        item = self._transcript.items[index]
        widget = self._build_widget(item)
        if widget is not None:
            self._column_layout.insertWidget(self._column_layout.count() - 1, widget)
        if index < len(self._widgets):
            self._widgets[index] = widget
        else:
            self._widgets.append(widget)
        if item.kind == KIND_USER and not self._rebuilding:
            self.turn_started.emit()

    def _build_widget(self, item: ChatItem) -> Optional[QWidget]:
        if item.kind == KIND_USER:
            return UserTurnWidget(item, self._scale, self._show_sender)
        if item.kind == KIND_ASSISTANT:
            return AssistantWidget(item, self._scale)
        return ActivityWidget(item, self._scale)

    # ------------------------------------------------------------------
    # Working ticker
    # ------------------------------------------------------------------

    def _sync_ticker(self) -> None:
        busy = self._transcript is not None and self._transcript.busy
        if busy and not self._ticker.isActive():
            self._ticker.start()
        elif not busy and self._ticker.isActive():
            self._ticker.stop()
        self.busy_changed.emit(busy)

    def _tick(self) -> None:
        for widget in self._widgets:
            if isinstance(widget, UserTurnWidget):
                widget.update_working_row()

    # ------------------------------------------------------------------
    # Scrolling
    # ------------------------------------------------------------------

    def _distance_from_bottom(self) -> int:
        bar = self._scroll.verticalScrollBar()
        return bar.maximum() - bar.value()

    def _on_scrolled(self, _value: int) -> None:
        self._follow = self._distance_from_bottom() < FOLLOW_THRESHOLD_PX
        self._jump.setVisible(not self._follow)

    def _on_range_changed(self, _minimum: int, maximum: int) -> None:
        if self._follow:
            self._scroll.verticalScrollBar().setValue(maximum)
        self._jump.setVisible(not self._follow and maximum > 0)

    def _jump_to_latest(self) -> None:
        self._follow = True
        bar = self._scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
        self._jump.setVisible(False)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._place_jump()

    def _place_jump(self) -> None:
        size = self._jump.sizeHint()
        self._jump.resize(size)
        self._jump.move((self.width() - size.width()) // 2, self.height() - size.height() - 24)
        self._jump.raise_()

    def eventFilter(self, obj, event):  # noqa: N802
        if obj is self._scroll.viewport() and event.type() == QEvent.Type.Wheel:
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                # Leave Ctrl+wheel to the properties panel zoom filter.
                return False
        return super().eventFilter(obj, event)
