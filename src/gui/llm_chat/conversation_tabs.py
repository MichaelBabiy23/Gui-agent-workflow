"""Tabbed Output page: one chat tab per real CLI conversation of a node."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QTabBar, QVBoxLayout, QWidget

from . import theme
from .chat_view import ChatView
from .conversations import (
    CONV_ADDED,
    CONV_RESET,
    CONV_TURN_STARTED,
    ChatConversations,
    conversation_label,
    conversation_tooltip,
)

BUSY_SUFFIX = " ●"


class ConversationTabs(QWidget):
    """A tab strip above a ``ChatView``; tabs mirror a ``ChatConversations``."""

    turn_started = Signal()
    busy_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._conversations: Optional[ChatConversations] = None
        self._show_sender = False
        self._scale = 1.0
        self._busy = False
        self.setObjectName("conversation_tabs")
        self.setStyleSheet(f"QWidget#conversation_tabs {{ background: {theme.BG}; }}")
        self.setAutoFillBackground(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._strip = QFrame()
        self._strip.setObjectName("conversation_strip")
        strip_layout = QHBoxLayout(self._strip)
        strip_layout.setContentsMargins(12, 0, 12, 0)
        strip_layout.setSpacing(0)
        self.tab_bar = QTabBar()
        self.tab_bar.setObjectName("conversation_tab_bar")
        self.tab_bar.setExpanding(False)
        self.tab_bar.setDrawBase(False)
        self.tab_bar.setUsesScrollButtons(True)
        self.tab_bar.setElideMode(Qt.TextElideMode.ElideRight)
        self.tab_bar.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tab_bar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tab_bar.currentChanged.connect(self._on_tab_changed)
        strip_layout.addWidget(self.tab_bar)
        strip_layout.addStretch(1)
        self._strip.setVisible(False)
        layout.addWidget(self._strip)

        self.chat_view = ChatView()
        layout.addWidget(self.chat_view, stretch=1)
        self.set_text_scale(1.0)

    # ------------------------------------------------------------------
    # Binding
    # ------------------------------------------------------------------

    def set_conversations(self, conversations: Optional[ChatConversations], show_sender: bool = False) -> None:
        if self._conversations is not None:
            self._conversations.remove_listener(self._on_change)
        self._conversations = conversations
        self._show_sender = show_sender
        if conversations is not None:
            conversations.add_listener(self._on_change)
        self._rebuild_tabs(select_latest=True)
        self._sync_busy()

    def conversations(self) -> Optional[ChatConversations]:
        return self._conversations

    def current_transcript(self):
        return self.chat_view.transcript()

    def set_text_scale(self, scale: float) -> None:
        self._scale = scale
        font_px = max(8, round(12 * scale))
        self.tab_bar.setFont(theme.ui_font(12, 500, scale))
        self._strip.setStyleSheet(
            f"QFrame#conversation_strip {{ background: {theme.BG}; border: none; "
            f"border-bottom: 1px solid {theme.LINE}; }}"
            f"QTabBar#conversation_tab_bar {{ background: transparent; }}"
            f"QTabBar#conversation_tab_bar::tab {{ background: transparent; color: {theme.MUTED}; "
            f"font-size: {font_px}px; padding: 7px 12px; border: none; margin-right: 2px; "
            f"border-bottom: 2px solid transparent; }}"
            f"QTabBar#conversation_tab_bar::tab:hover {{ color: {theme.TEXT}; }}"
            f"QTabBar#conversation_tab_bar::tab:selected {{ color: {theme.TEXT}; "
            f"border-bottom: 2px solid {theme.ACCENT}; }}"
            f"QTabBar#conversation_tab_bar QToolButton {{ background: {theme.BG}; border: none; color: {theme.MUTED}; }}"
        )
        self.chat_view.set_text_scale(scale)

    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------

    def _tab_text(self, index: int) -> str:
        text = conversation_label(index)
        if self._conversations is not None and 0 <= index < len(self._conversations):
            if self._conversations.items[index].busy:
                text += BUSY_SUFFIX
        return text

    def _rebuild_tabs(self, select_latest: bool) -> None:
        self.tab_bar.blockSignals(True)
        try:
            while self.tab_bar.count():
                self.tab_bar.removeTab(0)
            items = self._conversations.items if self._conversations is not None else []
            for index, transcript in enumerate(items):
                self.tab_bar.addTab(self._tab_text(index))
                self.tab_bar.setTabToolTip(index, conversation_tooltip(transcript))
            if items:
                self.tab_bar.setCurrentIndex(len(items) - 1 if select_latest else max(0, self.tab_bar.currentIndex()))
        finally:
            self.tab_bar.blockSignals(False)
        self._strip.setVisible(bool(items))
        self._bind_current()

    def _refresh_tab(self, index: int) -> None:
        if self._conversations is None or not (0 <= index < self.tab_bar.count()):
            return
        self.tab_bar.setTabText(index, self._tab_text(index))
        self.tab_bar.setTabToolTip(index, conversation_tooltip(self._conversations.items[index]))

    def _bind_current(self) -> None:
        index = self.tab_bar.currentIndex()
        transcript = None
        if self._conversations is not None and 0 <= index < len(self._conversations):
            transcript = self._conversations.items[index]
        if transcript is not self.chat_view.transcript() or transcript is None:
            self.chat_view.set_transcript(transcript, show_sender=self._show_sender)

    def _on_tab_changed(self, _index: int) -> None:
        self._bind_current()

    def select_conversation(self, index: int) -> None:
        if 0 <= index < self.tab_bar.count():
            self.tab_bar.setCurrentIndex(index)

    # ------------------------------------------------------------------
    # Conversation changes
    # ------------------------------------------------------------------

    def _on_change(self, change: str, index: int) -> None:
        if change == CONV_RESET:
            self._rebuild_tabs(select_latest=True)
        elif change == CONV_ADDED:
            self._rebuild_tabs(select_latest=False)
        elif change == CONV_TURN_STARTED:
            self.select_conversation(index)
            self.turn_started.emit()
        else:
            self._refresh_tab(index)
        self._sync_busy()

    def _sync_busy(self) -> None:
        busy = self._conversations is not None and self._conversations.busy
        if busy != self._busy:
            self._busy = busy
            self.busy_changed.emit(busy)
