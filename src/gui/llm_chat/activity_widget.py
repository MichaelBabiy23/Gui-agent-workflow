"""Collapsible tool-activity row (the Skylyx ``ToolActivity`` component)."""

from __future__ import annotations

import json
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.llm.stream_events import LEVEL_ERROR, LEVEL_INFO, LEVEL_WARNING

from . import theme
from .common_widgets import ChevronLabel, IconLabel, PreBox, ShineLabel
from .transcript import KIND_DIAGNOSTIC, ChatItem

KIND_COMMAND = "command"
KIND_EDIT = "edit"
KIND_READ = "read"
KIND_THINKING = "thinking"
KIND_DIAG = "diagnostic"
KIND_SEARCH = "search"
KIND_TOOL = "tool"

_ICONS = {
    KIND_COMMAND: theme.ICON_COMMAND,
    KIND_EDIT: theme.ICON_EDIT,
    KIND_READ: theme.ICON_READ,
    KIND_THINKING: theme.ICON_THINKING,
    KIND_SEARCH: theme.ICON_SEARCH,
    KIND_DIAG: theme.ICON_DIAGNOSTIC,
    KIND_TOOL: theme.ICON_TOOL,
}

_EDIT_NAMES = {"edit", "write", "multiedit", "notebookedit", "patch", "apply_patch", "file_change", "filechange"}
_READ_NAMES = {"read", "glob", "grep", "ls", "list", "cat", "view"}
_SEARCH_NAMES = {"websearch", "webfetch", "web_search", "fetch"}


def _command_text(item: ChatItem) -> str:
    if item.command:
        return item.command
    if isinstance(item.input, dict):
        command = item.input.get("command") or item.input.get("cmd")
        if isinstance(command, list):
            return " ".join(str(c) for c in command)
        if isinstance(command, str):
            return command
    return ""


def _path_text(item: ChatItem) -> str:
    if item.path:
        return item.path
    if isinstance(item.input, dict):
        for key in ("file_path", "filePath", "path"):
            value = item.input.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return ""


def _script_text(item: ChatItem) -> Optional[str]:
    if not isinstance(item.input, dict):
        return None
    for key in ("code", "script"):
        value = item.input.get(key)
        if isinstance(value, str):
            return value
    if item.name.lower() == "write":
        content = item.input.get("content")
        if isinstance(content, str):
            return content
    return None


def classify(item: ChatItem) -> tuple[str, str, str]:
    """Return ``(kind, title, detail)`` following ToolActivity's rules."""
    name = (item.name or "").strip()
    lowered = name.lower()
    command = _command_text(item)
    path = _path_text(item)
    if item.kind == KIND_DIAGNOSTIC:
        titles = {LEVEL_WARNING: "Warning", LEVEL_ERROR: "Error", LEVEL_INFO: "Info"}
        first_line = (item.text or "").split("\n")[0]
        return KIND_DIAG, titles.get(item.level, "Diagnostic"), first_line
    if command:
        return KIND_COMMAND, "Ran command", command
    if lowered in {"file_change", "filechange"}:
        return KIND_EDIT, "Changed files", ", ".join(item.changes)
    if lowered in _EDIT_NAMES:
        return KIND_EDIT, "Edited file", path
    if lowered in _READ_NAMES:
        return KIND_READ, "Read file", path
    if lowered in {"reasoning", "thinking"}:
        return KIND_THINKING, "Thinking", (item.text or "").split("\n")[0]
    if lowered in _SEARCH_NAMES:
        query = ""
        if isinstance(item.input, dict):
            query = str(item.input.get("query") or item.input.get("url") or "")
        return KIND_SEARCH, name, query or path
    return KIND_TOOL, name or "tool", path


class _SummaryRow(QFrame):
    """Clickable header row with hover background."""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("activity_summary")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMinimumHeight(26)
        self._apply_style(False)

    def _apply_style(self, hover: bool) -> None:
        background = theme.ROW_HOVER if hover else "transparent"
        self.setStyleSheet(
            f"QFrame#activity_summary {{ background: {background}; border-radius: 8px; border: none; }}"
        )

    def enterEvent(self, event) -> None:  # noqa: N802
        self._apply_style(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._apply_style(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class ActivityWidget(QWidget):
    """One collapsible ``details`` row: icon, title, detail, flag, chevron, body."""

    def __init__(self, item: ChatItem, scale: float = 1.0, parent=None):
        super().__init__(parent)
        self._item = item
        self._scale = scale
        self._open = False
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._summary = _SummaryRow()
        summary_layout = QHBoxLayout(self._summary)
        summary_layout.setContentsMargins(2, 2, 4, 2)
        summary_layout.setSpacing(6)
        self._icon = IconLabel(theme.ICON_TOOL, theme.ACTIVITY_ICON, 16, 24)
        summary_layout.addWidget(self._icon)
        self._title = ShineLabel("")
        self._title.set_colors(theme.ACTIVITY_TITLE, theme.TEXT)
        summary_layout.addWidget(self._title)
        self._detail = ShineLabel("")
        self._detail.set_elide(True)
        self._detail.set_colors(theme.MUTED, theme.MUTED)
        summary_layout.addWidget(self._detail, stretch=1)
        self._flag = QLabel("×")
        self._flag.setToolTip("Failed")
        self._flag.setVisible(False)
        summary_layout.addWidget(self._flag)
        self._chevron = ChevronLabel()
        summary_layout.addWidget(self._chevron)
        self._summary.clicked.connect(self.toggle)
        layout.addWidget(self._summary)

        self._body = QFrame()
        self._body.setObjectName("activity_body")
        self._body.setStyleSheet(
            f"QFrame#activity_body {{ background: {theme.ACTIVITY_BODY_BG}; border-radius: 8px; border: none; }}"
        )
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(12, 8, 12, 8)
        self._body_layout.setSpacing(0)
        self._body.setVisible(False)
        body_wrap = QHBoxLayout()
        body_wrap.setContentsMargins(30, 2, 0, 6)
        body_wrap.addWidget(self._body)
        layout.addLayout(body_wrap)

        self.refresh(item)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def set_text_scale(self, scale: float) -> None:
        self._scale = scale
        self.refresh(self._item)

    def refresh(self, item: ChatItem) -> None:
        self._item = item
        kind, title, detail = classify(item)
        failed = item.failed
        running = item.running
        icon_color = theme.DIFF_REMOVE if failed else theme.ACTIVITY_ICON
        self._icon._body = _ICONS.get(kind, theme.ICON_TOOL)
        self._icon.set_color(icon_color)
        self._icon._refresh()
        self._title.setFont(theme.ui_font(13.5, 500, self._scale))
        self._title.set_text(title)
        self._title.set_shining(running)
        self._detail.setFont(theme.code_font(12.5, self._scale))
        self._detail.set_text(detail)
        self._flag.setFont(theme.ui_font(13.5, 600, self._scale))
        self._flag.setStyleSheet(f"color: {theme.DIFF_REMOVE};")
        self._flag.setVisible(failed)
        self._summary.setMinimumHeight(max(26, round(26 * self._scale)))
        if self._open:
            self._rebuild_body()

    def toggle(self) -> None:
        self._open = not self._open
        self._chevron.set_open(self._open)
        if self._open:
            self._rebuild_body()
        self._body.setVisible(self._open and self._body_layout.count() > 0)

    def _clear_body(self) -> None:
        while self._body_layout.count():
            child = self._body_layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()

    def _section(self, label: str, text: str, top_margin: bool) -> None:
        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 12 if top_margin else 0, 0, 0)
        wrapper_layout.setSpacing(6)
        strong = QLabel(label)
        strong.setFont(theme.ui_font(12, 600, self._scale))
        strong.setStyleSheet(f"color: {theme.MUTED};")
        wrapper_layout.addWidget(strong)
        pre = PreBox(text, font=theme.code_font(12.5, self._scale))
        wrapper_layout.addWidget(pre)
        self._body_layout.addWidget(wrapper)

    def _hint(self, text: str) -> None:
        hint = QLabel(text)
        hint.setWordWrap(True)
        hint.setFont(theme.ui_font(12, scale=self._scale))
        hint.setStyleSheet(f"color: {theme.MUTED}; margin-top: 6px;")
        self._body_layout.addWidget(hint)

    def _rebuild_body(self) -> None:
        self._clear_body()
        item = self._item
        command = _command_text(item)
        sections = 0
        if command:
            self._section("Command", command, sections > 0)
            sections += 1
        if item.cwd:
            self._hint(f"Working directory: {item.cwd}")
        script = _script_text(item)
        if script is not None:
            self._section("Script / file contents", script, sections > 0)
            sections += 1
        if item.changes and not command:
            self._section("Changed files", "\n".join(item.changes), sections > 0)
            sections += 1
        if isinstance(item.input, dict) and "old_string" in item.input:
            self._edit_preview(str(item.input.get("old_string") or ""), str(item.input.get("new_string") or ""))
        if item.input is not None:
            body = item.input if isinstance(item.input, str) else json.dumps(item.input, indent=2, ensure_ascii=False)
            self._section("Input", body, sections > 0)
            sections += 1
        output = item.output if item.output else (item.text if item.kind != KIND_DIAGNOSTIC else "")
        if item.kind == KIND_DIAGNOSTIC and "\n" in (item.text or ""):
            output = item.text
        if output:
            self._section("Output", output, sections > 0)
            sections += 1
        if item.exit_code is not None:
            self._hint(f"Exit code {item.exit_code}")
        self._body.setVisible(self._open and self._body_layout.count() > 0)

    def _edit_preview(self, old: str, new: str) -> None:
        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 8, 0, 0)
        wrapper_layout.setSpacing(0)
        removed = PreBox(old, font=theme.code_font(12.5, self._scale))
        removed.setStyleSheet(
            "QPlainTextEdit { background: rgba(232, 131, 139, 0.12); border: none; "
            f"border-top-left-radius: 6px; border-top-right-radius: 6px; padding: 6px 8px; color: {theme.TEXT}; }}"
        )
        added = PreBox(new, font=theme.code_font(12.5, self._scale))
        added.setStyleSheet(
            "QPlainTextEdit { background: rgba(105, 189, 141, 0.12); border: none; "
            f"border-bottom-left-radius: 6px; border-bottom-right-radius: 6px; padding: 6px 8px; color: {theme.TEXT}; }}"
        )
        wrapper_layout.addWidget(removed)
        wrapper_layout.addWidget(added)
        self._body_layout.addWidget(wrapper)
