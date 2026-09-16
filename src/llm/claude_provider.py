"""Claude CLI provider."""

import json
from typing import Iterable, List, Optional, Tuple
from .base_provider import (
    BaseLLMProvider,
    LLMProviderRegistry,
    ModelEntry,
    effort_variants,
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
    stringify_output,
)


THINKING_REQUIRED_EFFORTS = frozenset({"xhigh", "max"})
ALWAYS_THINKING_SETTINGS_JSON = '{"alwaysThinkingEnabled": true}'


class ClaudeProvider(BaseLLMProvider):
    ENTRIES = [
        ModelEntry(
            model_id="claude-opus-5",
            label="Claude Opus 5",
            variants=effort_variants("low", "medium", "high", "xhigh", "max"),
            default_variant_id="high",
        ),
        ModelEntry(
            model_id="claude-sonnet-5",
            label="Claude Sonnet 5",
            variants=effort_variants("low", "medium", "high", "xhigh"),
            default_variant_id="medium",
        ),
    ]

    @property
    def name(self) -> str:
        return "claude"

    @property
    def display_name(self) -> str:
        return "Claude"

    def get_model_entries(self) -> List[ModelEntry]:
        return self.ENTRIES

    def build_command(self, prompt: str, model: Optional[str] = None,
                      working_directory: Optional[str] = None,
                      session_id: Optional[str] = None) -> List[str]:
        _ = working_directory
        # stream-json emits every assistant message, tool call, and tool
        # result as its own line while the turn runs; --verbose is required
        # for stream-json in print mode.
        cmd = [
            "claude",
            "--dangerously-skip-permissions",
            "--output-format",
            "stream-json",
            "--verbose",
        ]
        actual_model = model
        effort = None
        if model and ":" in model:
            actual_model, effort = model.split(":", 1)

        if actual_model:
            cmd.extend(["--model", actual_model])
        if effort:
            cmd.extend(["--effort", effort])
        if effort in THINKING_REQUIRED_EFFORTS:
            cmd.extend(["--settings", ALWAYS_THINKING_SETTINGS_JSON])
        if session_id:
            cmd.extend(["--resume", session_id])
        cmd.append("-p")
        return cmd

    def supports_session_resume(self, model: Optional[str] = None) -> bool:
        _ = model
        return True

    def supports_profiles(self) -> bool:
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
        text = str(line).strip()
        if not text:
            return []
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return diagnostic_from_plain_line(text)
        if not isinstance(payload, dict):
            return []

        event_type = str(payload.get("type", "")).strip().lower()
        if event_type == "system":
            session_id = payload.get("session_id")
            if payload.get("subtype") == "init" and isinstance(session_id, str) and session_id:
                return [StreamEvent(kind=EVENT_SESSION, session_id=session_id)]
            return []

        if event_type == "assistant":
            return self._assistant_events(payload.get("message"))

        if event_type == "user":
            return self._tool_result_events(payload.get("message"))

        if event_type == "result":
            # The final result text (success or error) is delivered through the
            # worker's finished/error signals and rendered on the turn itself.
            return []

        if event_type == "error":
            message = payload.get("error") or payload.get("message")
            if isinstance(message, dict):
                message = message.get("message")
            if isinstance(message, str) and message.strip():
                return [diagnostic_event(message.strip(), LEVEL_ERROR)]
        return []

    def _assistant_events(self, message: object) -> List[StreamEvent]:
        if not isinstance(message, dict):
            return []
        message_id = str(message.get("id") or "")
        content = message.get("content")
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        if not isinstance(content, list):
            return []
        events: List[StreamEvent] = []
        for index, part in enumerate(content):
            if not isinstance(part, dict):
                continue
            part_type = str(part.get("type", "")).lower()
            if part_type == "text":
                body = part.get("text")
                if isinstance(body, str) and body.strip():
                    events.append(
                        StreamEvent(
                            kind=EVENT_ASSISTANT,
                            item_id=f"{message_id}:{index}" if message_id else "",
                            text=body,
                        )
                    )
            elif part_type == "tool_use":
                tool_input = part.get("input")
                events.append(
                    StreamEvent(
                        kind=EVENT_TOOL,
                        item_id=str(part.get("id") or ""),
                        name=str(part.get("name") or "tool"),
                        status=TOOL_RUNNING,
                        input=tool_input,
                        command=self._command_from_input(tool_input),
                        path=self._path_from_input(tool_input),
                    )
                )
        return events

    def _tool_result_events(self, message: object) -> List[StreamEvent]:
        if not isinstance(message, dict):
            return []
        content = message.get("content")
        if not isinstance(content, list):
            return []
        events: List[StreamEvent] = []
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "tool_result":
                continue
            events.append(
                StreamEvent(
                    kind=EVENT_TOOL,
                    item_id=str(part.get("tool_use_id") or ""),
                    status=TOOL_FAILED if part.get("is_error") else TOOL_COMPLETED,
                    output=stringify_output(part.get("content")),
                )
            )
        return events

    @staticmethod
    def _command_from_input(tool_input: object) -> str:
        if isinstance(tool_input, dict):
            command = tool_input.get("command") or tool_input.get("cmd")
            if isinstance(command, list):
                return " ".join(str(c) for c in command)
            if isinstance(command, str):
                return command
        return ""

    @staticmethod
    def _path_from_input(tool_input: object) -> str:
        if isinstance(tool_input, dict):
            for key in ("file_path", "path", "notebook_path", "pattern", "url"):
                value = tool_input.get(key)
                if isinstance(value, str) and value.strip():
                    return value
        return ""

    def parse_structured_output(self, lines: Iterable[str]) -> Tuple[str, str]:
        session_id = ""
        text_candidates: List[str] = []
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
            result = payload.get("result") if isinstance(payload, dict) else None
            if isinstance(result, str) and result.strip():
                text_candidates.append(result.strip())
                continue
            message = payload.get("message") if isinstance(payload, dict) else None
            if isinstance(message, str) and message.strip():
                text_candidates.append(message.strip())
                continue
            if isinstance(payload, dict):
                flattened = self._flatten_text(payload.get("content"))
                joined = "\n".join(part.strip() for part in flattened if part and part.strip()).strip()
                if joined:
                    text_candidates.append(joined)
        if text_candidates:
            return text_candidates[-1], session_id
        return "", session_id


LLMProviderRegistry.register(ClaudeProvider())
