"""In-memory chat transcript for one LLM conversation.

A ``ChatTranscript`` is the ordered list of items shown in the LLM node's
Output view: user turns (the prompts the workflow sent), assistant text,
tool activity rows, and diagnostics. It is provider-neutral; the canvas
folds ``StreamEvent`` objects into it while a call runs and marks the turn
finished when the worker completes.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Tuple

from src.llm.stream_events import (
    EVENT_ASSISTANT,
    EVENT_ASSISTANT_DELTA,
    EVENT_DIAGNOSTIC,
    EVENT_TOOL,
    LEVEL_INFO,
    StreamEvent,
)

KIND_USER = "user"
KIND_ASSISTANT = "assistant"
KIND_TOOL = "tool"
KIND_DIAGNOSTIC = "diagnostic"

TURN_COMPLETED = "completed"
TURN_FAILED = "failed"
TURN_INTERRUPTED = "interrupted"

CHANGE_APPEND = "append"
CHANGE_UPDATE = "update"
CHANGE_RESET = "reset"

ChangeListener = Callable[[str, int], None]


@dataclass
class ChatItem:
    kind: str
    text: str = ""
    name: str = ""
    item_id: str = ""
    input: Any = None
    output: str = ""
    command: str = ""
    path: str = ""
    cwd: str = ""
    exit_code: Optional[int] = None
    changes: Tuple[str, ...] = field(default_factory=tuple)
    status: str = ""
    level: str = LEVEL_INFO
    sender: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    duration_ms: int = 0
    error: str = ""

    @property
    def is_busy_turn(self) -> bool:
        return self.kind == KIND_USER and not self.finished_at

    @property
    def failed(self) -> bool:
        if self.status == TURN_FAILED:
            return True
        return self.exit_code is not None and self.exit_code != 0

    @property
    def running(self) -> bool:
        return self.status in {"running", "in_progress"}


class ChatTranscript:
    """Ordered chat items plus change notifications for the view."""

    def __init__(self) -> None:
        self.items: List[ChatItem] = []
        self._listeners: List[ChangeListener] = []

    # ------------------------------------------------------------------
    # Listeners
    # ------------------------------------------------------------------

    def add_listener(self, listener: ChangeListener) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: ChangeListener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify(self, change: str, index: int) -> None:
        for listener in list(self._listeners):
            listener(change, index)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def busy(self) -> bool:
        return any(item.is_busy_turn for item in self.items)

    def busy_since(self) -> float:
        for item in reversed(self.items):
            if item.is_busy_turn:
                return item.started_at
        return 0.0

    def is_empty(self) -> bool:
        return not self.items

    def find_index(self, kind: str, item_id: str) -> int:
        if not item_id:
            return -1
        for index in range(len(self.items) - 1, -1, -1):
            item = self.items[index]
            if item.kind == kind and item.item_id == item_id:
                return index
        return -1

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def clear(self) -> None:
        self.items.clear()
        self._notify(CHANGE_RESET, -1)

    def _append(self, item: ChatItem) -> int:
        self.items.append(item)
        index = len(self.items) - 1
        self._notify(CHANGE_APPEND, index)
        return index

    def add_user_turn(self, text: str, *, turn_id: str, sender: str = "") -> int:
        return self._append(
            ChatItem(
                kind=KIND_USER,
                text=text,
                item_id=turn_id,
                sender=sender,
                started_at=time.time(),
            )
        )

    def add_assistant(self, text: str, item_id: str = "") -> int:
        index = self.find_index(KIND_ASSISTANT, item_id)
        if index >= 0:
            self.items[index].text = text
            self._notify(CHANGE_UPDATE, index)
            return index
        return self._append(ChatItem(kind=KIND_ASSISTANT, text=text, item_id=item_id))

    def append_assistant_delta(self, delta: str, item_id: str = "") -> int:
        index = self.find_index(KIND_ASSISTANT, item_id)
        if index < 0 and self.items and self.items[-1].kind == KIND_ASSISTANT and not item_id:
            index = len(self.items) - 1
        if index >= 0:
            self.items[index].text += delta
            self._notify(CHANGE_UPDATE, index)
            return index
        return self._append(ChatItem(kind=KIND_ASSISTANT, text=delta, item_id=item_id))

    def add_diagnostic(self, text: str, level: str = LEVEL_INFO) -> int:
        return self._append(ChatItem(kind=KIND_DIAGNOSTIC, text=text, level=level))

    def upsert_tool(self, event: StreamEvent) -> int:
        index = self.find_index(KIND_TOOL, event.item_id)
        if index < 0:
            item = ChatItem(kind=KIND_TOOL, item_id=event.item_id, name=event.name or "tool")
            index = self._append(item)
            changed = CHANGE_APPEND
        else:
            item = self.items[index]
            changed = CHANGE_UPDATE
        if event.name:
            item.name = event.name
        if event.status:
            item.status = event.status
        if event.input is not None:
            item.input = event.input
        if event.output is not None:
            item.output = event.output
        if event.command:
            item.command = event.command
        if event.path:
            item.path = event.path
        if event.cwd:
            item.cwd = event.cwd
        if event.exit_code is not None:
            item.exit_code = event.exit_code
        if event.changes:
            item.changes = tuple(event.changes)
        if changed == CHANGE_UPDATE:
            self._notify(CHANGE_UPDATE, index)
        return index

    def apply_event(self, event: StreamEvent) -> None:
        if event.kind == EVENT_ASSISTANT:
            self.add_assistant(event.text, event.item_id)
        elif event.kind == EVENT_ASSISTANT_DELTA:
            self.append_assistant_delta(event.text, event.item_id)
        elif event.kind == EVENT_TOOL:
            self.upsert_tool(event)
        elif event.kind == EVENT_DIAGNOSTIC:
            self.add_diagnostic(event.text, event.level)

    def turn_has_assistant_text(self, turn_id: str) -> bool:
        start = self.find_index(KIND_USER, turn_id)
        for item in self.items[start + 1:] if start >= 0 else self.items:
            if item.kind == KIND_ASSISTANT and item.text.strip():
                return True
        return False

    def finish_turn(self, turn_id: str, status: str = TURN_COMPLETED, error: str = "") -> None:
        index = self.find_index(KIND_USER, turn_id)
        if index < 0:
            for candidate in range(len(self.items) - 1, -1, -1):
                if self.items[candidate].is_busy_turn:
                    index = candidate
                    break
        if index < 0:
            return
        turn = self.items[index]
        if not turn.finished_at:
            turn.finished_at = time.time()
            turn.duration_ms = max(0, int((turn.finished_at - (turn.started_at or turn.finished_at)) * 1000))
        turn.status = status
        if status == TURN_FAILED:
            turn.error = error or turn.error or "The agent exited before completing the turn."
        else:
            turn.error = error or ""
        for tool_index, item in enumerate(self.items[index + 1:], start=index + 1):
            if item.kind == KIND_TOOL and item.running:
                item.status = TURN_FAILED if status == TURN_FAILED else TURN_INTERRUPTED
                self._notify(CHANGE_UPDATE, tool_index)
        self._notify(CHANGE_UPDATE, index)

    def interrupt_open_turns(self) -> None:
        for item in list(self.items):
            if item.is_busy_turn:
                self.finish_turn(item.item_id, TURN_INTERRUPTED)
