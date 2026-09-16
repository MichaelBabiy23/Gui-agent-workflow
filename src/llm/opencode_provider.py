"""OpenCode CLI provider (free OpenCode Zen models)."""

import json
import re
from pathlib import Path
from typing import Iterable, List, Optional, Tuple
from .base_provider import (
    BaseLLMProvider,
    LLMProviderRegistry,
    ModelEntry,
)
from .stream_events import (
    EVENT_ASSISTANT,
    EVENT_SESSION,
    EVENT_TOOL,
    LEVEL_ERROR,
    StreamEvent,
    TOOL_COMPLETED,
    TOOL_FAILED,
    TOOL_RUNNING,
    diagnostic_event,
    diagnostic_from_plain_line,
)


_ZEN_PROVIDER_PREFIX = "opencode"
_ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


class OpenCodeProvider(BaseLLMProvider):
    ENTRIES = [
        ModelEntry(model_id="big-pickle", label="Big Pickle"),
        ModelEntry(model_id="mimo-v2.5-free", label="MiMo-V2.5 Free"),
        ModelEntry(model_id="ling-3.0-flash-fin-free", label="Ling 3.0 Flash Fin Free"),
        ModelEntry(model_id="nemotron-3-ultra-free", label="Nemotron 3 Ultra Free"),
        ModelEntry(model_id="nemotron-3.5-lightning-free", label="Nemotron 3.5 Lightning Free"),
        ModelEntry(model_id="muse-spark-1.3-contributor-free", label="Muse Spark 1.3 Contributor Free"),
    ]

    @property
    def name(self) -> str:
        return "opencode"

    @property
    def display_name(self) -> str:
        return "OpenCode"

    def get_model_entries(self) -> List[ModelEntry]:
        return self.ENTRIES

    @property
    def uses_stdin(self) -> bool:
        return False

    def build_command(self, prompt: str, model: Optional[str] = None,
                      working_directory: Optional[str] = None,
                      session_id: Optional[str] = None) -> List[str]:
        cmd = ["opencode", "run", "--format", "json", "--auto"]

        normalized_wd: Optional[str] = None
        if working_directory and str(working_directory).strip():
            candidate = Path(working_directory)
            if candidate.exists() and candidate.is_dir():
                normalized_wd = str(candidate)
        if normalized_wd:
            cmd.extend(["--dir", normalized_wd])

        if model and model.strip():
            cmd.extend(["--model", f"{_ZEN_PROVIDER_PREFIX}/{model.strip()}"])

        if session_id and session_id.strip():
            cmd.extend(["--session", session_id.strip()])

        cmd.append(prompt)
        return cmd

    def supports_session_resume(self, model: Optional[str] = None) -> bool:
        _ = model
        return True

    def uses_structured_output(self, model: Optional[str] = None) -> bool:
        _ = model
        return True

    def structured_output_events(
        self,
        line: str,
        model: Optional[str] = None,
    ) -> List[StreamEvent]:
        _ = model
        text = _strip_ansi(str(line)).strip()
        if not text:
            return []
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return diagnostic_from_plain_line(text)
        if not isinstance(payload, dict):
            return []

        event_type = str(payload.get("type", "")).strip().lower()
        part = payload.get("part")
        events: List[StreamEvent] = []
        session_id = self._find_session_id(payload)
        if session_id:
            events.append(StreamEvent(kind=EVENT_SESSION, session_id=session_id))

        if event_type == "error":
            message = self._extract_error_message(payload)
            if message:
                events.append(diagnostic_event(message, LEVEL_ERROR))
            return events

        if event_type == "text" and isinstance(part, dict):
            body = part.get("text")
            if isinstance(body, str) and body.strip():
                events.append(
                    StreamEvent(
                        kind=EVENT_ASSISTANT,
                        item_id=str(part.get("id") or ""),
                        text=body,
                    )
                )
            return events

        if event_type == "tool_use" and isinstance(part, dict):
            events.append(self._tool_event(part))
        return events

    def _tool_event(self, part: dict) -> StreamEvent:
        tool_name = str(part.get("tool", "")).strip() or "tool"
        state = part.get("state") if isinstance(part.get("state"), dict) else {}
        raw_status = str(state.get("status", "")).strip().lower()
        if raw_status == "error":
            status = TOOL_FAILED
        elif raw_status == "completed":
            status = TOOL_COMPLETED
        else:
            status = TOOL_RUNNING
        tool_input = state.get("input")
        command = ""
        path = ""
        if isinstance(tool_input, dict):
            raw_command = tool_input.get("command")
            if isinstance(raw_command, list):
                command = " ".join(str(c) for c in raw_command)
            elif isinstance(raw_command, str):
                command = raw_command
            for key in ("filePath", "file_path", "path", "pattern", "url"):
                value = tool_input.get(key)
                if isinstance(value, str) and value.strip():
                    path = value
                    break
        output = state.get("output")
        if status == TOOL_FAILED:
            error_text = self._first_non_empty_text(state.get("error"))
            if error_text:
                output = error_text
        if output is not None and not isinstance(output, str):
            output = json.dumps(output, indent=2, ensure_ascii=False)
        metadata = state.get("metadata")
        exit_code = metadata.get("exit") if isinstance(metadata, dict) else None
        return StreamEvent(
            kind=EVENT_TOOL,
            item_id=str(part.get("id") or part.get("callID") or ""),
            name=tool_name,
            status=status,
            input=tool_input,
            command=command,
            path=path,
            output=output,
            exit_code=exit_code if isinstance(exit_code, int) else None,
        )

    def parse_structured_output(self, lines: Iterable[str]) -> Tuple[str, str]:
        session_id = ""
        text_parts: List[str] = []
        error_messages: List[str] = []
        for line in lines:
            text = str(line).strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            candidate = self._find_session_id(payload)
            if candidate:
                session_id = candidate
            if not isinstance(payload, dict):
                continue
            event_type = str(payload.get("type", "")).strip().lower()
            part = payload.get("part")
            if event_type == "error":
                message = self._extract_error_message(payload)
                if message:
                    error_messages.append(message)
            elif isinstance(part, dict) and str(part.get("type", "")).strip().lower() == "text":
                body = part.get("text")
                if isinstance(body, str) and body.strip():
                    text_parts.append(body.strip())
        if text_parts:
            return "\n".join(text_parts), session_id
        if error_messages:
            return "; ".join(dict.fromkeys(error_messages)), session_id
        return "", session_id

    def _find_session_id(self, payload: object) -> str:
        if isinstance(payload, dict):
            for key in ("sessionID", "sessionId"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return super()._find_session_id(payload)

    def _extract_error_message(self, payload: dict) -> str:
        name = ""
        detail = ""
        error = payload.get("error")
        if isinstance(error, dict):
            name = self._first_non_empty_text(error.get("name"))
            data = error.get("data")
            if isinstance(data, dict):
                detail = self._first_non_empty_text(data.get("message"))
            if not detail:
                detail = self._first_non_empty_text(
                    error.get("message"),
                    error.get("detail"),
                )
        if not name:
            name = self._first_non_empty_text(payload.get("name"))
        if not detail:
            detail = self._first_non_empty_text(payload.get("message"))
        if name and detail and detail != name:
            return f"{name}: {detail}"
        return name or detail

    def _first_non_empty_text(self, *values: object) -> str:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, (int, float, bool)):
                return str(value)
            if isinstance(value, list):
                flattened = [
                    part.strip()
                    for part in self._flatten_text(value)
                    if isinstance(part, str) and part.strip()
                ]
                if flattened:
                    return flattened[0]
        return ""


def _strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE_PATTERN.sub("", text)


LLMProviderRegistry.register(OpenCodeProvider())
