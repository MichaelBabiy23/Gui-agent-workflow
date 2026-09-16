"""Per-node set of chat conversations, one per real CLI chat.

An LLM node can be called many times in one run (loop bodies, fan-in from
several parents, repeated runs). Each call either resumes an existing CLI
session or opens a brand-new chat with the provider. ``ChatConversations``
keeps one ``ChatTranscript`` per real chat so the Output page can show them
as separate tabs instead of pretending unrelated calls were one thread.

A conversation is identified by ``conversation_id`` (a UUID the canvas
creates when a call opens a new chat; mirrored nodes of a named session
share the same id) and, once the provider reports it, by ``session_id``.
"""

from __future__ import annotations

from typing import Callable, List, Optional

from .transcript import CHANGE_APPEND, KIND_USER, ChatTranscript

CONV_ADDED = "added"
CONV_RESET = "reset"
CONV_CHANGED = "changed"
CONV_TURN_STARTED = "turn_started"

ConversationListener = Callable[[str, int], None]


def conversation_label(index: int) -> str:
    return f"Chat {index + 1}"


def conversation_tooltip(transcript: ChatTranscript) -> str:
    if transcript.session_id:
        return f"CLI session {transcript.session_id}"
    return "New CLI chat (no session id captured yet)"


class ChatConversations:
    """Ordered ``ChatTranscript`` objects plus change notifications."""

    def __init__(self) -> None:
        self._items: List[ChatTranscript] = []
        self._listeners: List[ConversationListener] = []

    # ------------------------------------------------------------------
    # Listeners
    # ------------------------------------------------------------------

    def add_listener(self, listener: ConversationListener) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: ConversationListener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify(self, change: str, index: int) -> None:
        for listener in list(self._listeners):
            listener(change, index)

    def _on_transcript_change(self, transcript: ChatTranscript, change: str, index: int) -> None:
        try:
            position = self._items.index(transcript)
        except ValueError:
            return
        if change == CHANGE_APPEND and 0 <= index < len(transcript.items):
            if transcript.items[index].kind == KIND_USER:
                self._notify(CONV_TURN_STARTED, position)
        self._notify(CONV_CHANGED, position)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def items(self) -> List[ChatTranscript]:
        return self._items

    def __len__(self) -> int:
        return len(self._items)

    @property
    def busy(self) -> bool:
        return any(transcript.busy for transcript in self._items)

    def index_of(self, conversation_id: str) -> int:
        for index, transcript in enumerate(self._items):
            if transcript.conversation_id == conversation_id:
                return index
        return -1

    def get(self, conversation_id: str) -> Optional[ChatTranscript]:
        index = self.index_of(conversation_id)
        return self._items[index] if index >= 0 else None

    def find_by_session(self, session_id: str) -> Optional[ChatTranscript]:
        session_id = session_id.strip()
        if not session_id:
            return None
        for transcript in reversed(self._items):
            if transcript.session_id == session_id:
                return transcript
        return None

    def latest(self) -> Optional[ChatTranscript]:
        return self._items[-1] if self._items else None

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def open(self, conversation_id: str, session_id: str = "") -> ChatTranscript:
        """Return the conversation with this id, creating it when missing."""
        existing = self.get(conversation_id)
        if existing is not None:
            return existing
        transcript = ChatTranscript(conversation_id=conversation_id, session_id=session_id.strip())
        transcript.add_listener(
            lambda change, index, _t=transcript: self._on_transcript_change(_t, change, index)
        )
        self._items.append(transcript)
        self._notify(CONV_ADDED, len(self._items) - 1)
        return transcript

    def set_session_id(self, conversation_id: str, session_id: str) -> None:
        index = self.index_of(conversation_id)
        if index < 0:
            return
        session_id = session_id.strip()
        if self._items[index].session_id == session_id:
            return
        self._items[index].session_id = session_id
        self._notify(CONV_CHANGED, index)

    def clear(self) -> None:
        self._items = []
        self._notify(CONV_RESET, -1)

    def interrupt_open_turns(self) -> None:
        for transcript in list(self._items):
            transcript.interrupt_open_turns()
