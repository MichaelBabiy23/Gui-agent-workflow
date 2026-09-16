"""User bubble, assistant message, and empty-state widgets for the chat view."""

from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .common_widgets import ShineLabel
from .markdown_view import MarkdownView
from .transcript import TURN_FAILED, TURN_INTERRUPTED, ChatItem


def format_duration(ms: float) -> str:
    total = max(0, int(ms // 1000))
    if total < 60:
        return f"{total}s"
    return f"{total // 60}m {total % 60:02d}s"


class UserTurnWidget(QWidget):
    """Right-aligned prompt bubble followed by the working/worked-for row."""

    def __init__(self, item: ChatItem, scale: float = 1.0, show_sender: bool = False, parent=None):
        super().__init__(parent)
        self._item = item
        self._scale = scale
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(0)

        self._sender = QLabel("")
        self._sender.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._sender.setVisible(show_sender)
        self._sender.setStyleSheet(f"color: {theme.MUTED}; margin-bottom: 4px;")
        layout.addWidget(self._sender)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addStretch(1)
        self._bubble = QFrame()
        self._bubble.setObjectName("msg_bubble")
        self._bubble.setStyleSheet(
            f"QFrame#msg_bubble {{ background: {theme.BUBBLE_BG}; border: 1px solid {theme.BUBBLE_BORDER}; "
            "border-radius: 16px; }"
        )
        bubble_layout = QVBoxLayout(self._bubble)
        bubble_layout.setContentsMargins(14, 10, 14, 10)
        bubble_layout.setSpacing(0)
        self._markdown = MarkdownView()
        bubble_layout.addWidget(self._markdown)
        row.addWidget(self._bubble)
        layout.addLayout(row)

        self._working = QFrame()
        self._working.setObjectName("working_row")
        self._working.setStyleSheet(
            f"QFrame#working_row {{ border: none; border-bottom: 1px solid {theme.LINE_SOFT}; }}"
        )
        working_layout = QHBoxLayout(self._working)
        working_layout.setContentsMargins(6, 0, 6, 0)
        working_layout.setSpacing(0)
        self._working_label = ShineLabel("")
        self._working_label.set_colors(theme.MUTED, theme.TEXT)
        working_layout.addWidget(self._working_label)
        working_layout.addStretch(1)
        layout.addWidget(self._working)

        self._error = QLabel("")
        self._error.setWordWrap(True)
        self._error.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._error.setStyleSheet(f"color: {theme.DIFF_REMOVE}; margin-top: 8px;")
        self._error.setVisible(False)
        layout.addWidget(self._error)

        layout.addSpacing(6)
        self.refresh(item)

    def set_text_scale(self, scale: float) -> None:
        self._scale = scale
        self.refresh(self._item)

    def refresh(self, item: ChatItem) -> None:
        self._item = item
        self._sender.setFont(theme.ui_font(11.5, 500, self._scale))
        self._sender.setText(item.sender)
        self._markdown.set_markdown(item.text, 14, 160, self._scale)
        self._working_label.setFont(theme.ui_font(13.5, scale=self._scale))
        self._working.setFixedHeight(max(28, round(28 * self._scale)))
        self._error.setFont(theme.ui_font(13.5, scale=self._scale))
        self.update_working_row()

    def update_working_row(self) -> None:
        item = self._item
        if item.finished_at:
            prefix = {
                TURN_FAILED: "Failed after",
                TURN_INTERRUPTED: "Stopped after",
            }.get(item.status, "Worked for")
            self._working_label.set_text(f"{prefix} {format_duration(item.duration_ms)}")
            self._working_label.set_shining(False)
            self._error.setText(item.error)
            self._error.setVisible(bool(item.error))
        else:
            elapsed_ms = (time.time() - (item.started_at or time.time())) * 1000
            self._working_label.set_text(f"Working for {format_duration(elapsed_ms)}")
            self._working_label.set_shining(True)
            self._error.setVisible(False)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._bubble.setMaximumWidth(max(80, int(self.width() * theme.BUBBLE_MAX_FRACTION)))


class AssistantWidget(QWidget):
    """Left-aligned assistant markdown block."""

    def __init__(self, item: ChatItem, scale: float = 1.0, parent=None):
        super().__init__(parent)
        self._item = item
        self._scale = scale
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 12)
        layout.setSpacing(0)
        self._markdown = MarkdownView()
        layout.addWidget(self._markdown)
        self.refresh(item)

    def set_text_scale(self, scale: float) -> None:
        self._scale = scale
        self.refresh(self._item)

    def refresh(self, item: ChatItem) -> None:
        self._item = item
        self._markdown.set_markdown(item.text, 14.5, 180, self._scale)


class EmptyStateWidget(QWidget):
    """Centered hint shown when the transcript has no items."""

    def __init__(self, text: str, scale: float = 1.0, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel(text)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        self._label.setStyleSheet(f"color: {theme.EMPTY_TEXT};")
        layout.addWidget(self._label)
        self.set_text_scale(scale)

    def set_text_scale(self, scale: float) -> None:
        self._label.setFont(theme.ui_font(13.5, scale=scale))
