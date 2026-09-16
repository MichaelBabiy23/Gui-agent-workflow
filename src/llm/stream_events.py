"""Provider-neutral live events parsed from structured CLI output.

Each provider turns one raw stdout line into zero or more ``StreamEvent``
objects while the subprocess is still running. The GUI folds those events
into a chat transcript (user turn, assistant text, tool activity rows,
diagnostics) without knowing any provider's JSON schema.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple


EVENT_SESSION = "session"
EVENT_ASSISTANT = "assistant"
EVENT_ASSISTANT_DELTA = "assistant_delta"
EVENT_TOOL = "tool"
EVENT_DIAGNOSTIC = "diagnostic"

TOOL_RUNNING = "running"
TOOL_COMPLETED = "completed"
TOOL_FAILED = "failed"

LEVEL_INFO = "info"
LEVEL_WARNING = "warning"
LEVEL_ERROR = "error"
LEVEL_DIAGNOSTIC = "diagnostic"


@dataclass
class StreamEvent:
    """One transcript mutation derived from a structured output line.

    ``kind`` selects how the GUI applies the event:

    - ``assistant``: full assistant text for ``item_id`` (upsert).
    - ``assistant_delta``: append ``text`` to the assistant item ``item_id``.
    - ``tool``: create or update the tool activity ``item_id``; ``None``
      fields leave the existing value untouched.
    - ``diagnostic``: one informational/warning/error note.
    - ``session``: the provider announced its resumable session id.
    """

    kind: str
    text: str = ""
    item_id: str = ""
    name: str = ""
    status: str = ""
    input: Any = None
    output: Optional[str] = None
    command: str = ""
    path: str = ""
    cwd: str = ""
    exit_code: Optional[int] = None
    changes: Tuple[str, ...] = field(default_factory=tuple)
    level: str = LEVEL_INFO
    session_id: str = ""


def diagnostic_event(text: str, level: str = LEVEL_DIAGNOSTIC) -> StreamEvent:
    return StreamEvent(kind=EVENT_DIAGNOSTIC, text=text, level=level)


def diagnostic_from_plain_line(line: str) -> List[StreamEvent]:
    """Map a non-JSON CLI line (usually stderr noise) onto a diagnostic.

    Structured log lines such as ``{"level":"WARN","fields":{"message":..}}``
    are unwrapped so the note shows the human-readable message and level.
    """
    text = str(line).strip()
    if not text:
        return []
    level = LEVEL_DIAGNOSTIC
    message = text
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        fields = payload.get("fields")
        candidate = fields.get("message") if isinstance(fields, dict) else None
        if not isinstance(candidate, str):
            candidate = payload.get("message")
        if isinstance(candidate, str) and candidate.strip():
            message = candidate.strip()
            level = _level_from_text(str(payload.get("level", "")))
    return [StreamEvent(kind=EVENT_DIAGNOSTIC, text=message, level=level)]


def _level_from_text(value: str) -> str:
    upper = value.strip().upper()
    if upper in {"WARN", "WARNING"}:
        return LEVEL_WARNING
    if upper == "ERROR":
        return LEVEL_ERROR
    if upper == "INFO":
        return LEVEL_INFO
    return LEVEL_DIAGNOSTIC


def stringify_output(value: Any) -> str:
    """Render a tool result payload as display text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: List[str] = []
        for part in value:
            if isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str):
                    parts.append(text)
                    continue
            parts.append(stringify_output(part))
        return "\n".join(p for p in parts if p)
    try:
        return json.dumps(value, indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)
