"""Shared node-output helpers for WorkflowCanvas execution.

Non-LLM nodes keep a plain-text ``output_text`` log. LLM nodes keep a
``ChatTranscript`` instead; the helpers here start a user turn when a call
is fired, fold live ``StreamEvent`` objects into it, and finish the turn
when the worker completes. Named-session output is mirrored: every LLM
node that saves to or resumes the same workflow session name receives the
same transcript operations, so selecting any of them shows one merged
conversation.
"""

from __future__ import annotations

from typing import Callable

from src.gui.llm_chat import TURN_COMPLETED, ChatTranscript
from src.gui.llm_node import LLMNode, WorkflowNode
from src.gui.llm_sessions.session_state import normalize_session_name
from src.gui.workflow_io import get_provider_for_model
from src.llm.stream_events import LEVEL_INFO, StreamEvent


def llm_shared_session_name(node: LLMNode) -> str:
    if node.resume_named_session_name.strip():
        return normalize_session_name(node.resume_named_session_name)
    if node.save_session_enabled and node.save_session_name.strip():
        return normalize_session_name(node.save_session_name)
    return ""


def llm_session_label(node: LLMNode) -> str:
    """Crumb text for the chat header: the shared session name or a local marker."""
    shared = llm_shared_session_name(node)
    if shared:
        return shared
    if node.resume_session_enabled:
        return "Node session"
    return "New session each run"


def iter_output_targets(canvas, node: WorkflowNode) -> list[WorkflowNode]:
    if not isinstance(node, LLMNode):
        return [node]
    session_name = llm_shared_session_name(node)
    if not session_name:
        return [node]
    targets: list[WorkflowNode] = []
    seen: set[str] = set()
    for candidate in canvas._nodes.values():
        if (
            isinstance(candidate, LLMNode)
            and llm_shared_session_name(candidate) == session_name
            and candidate.node_id not in seen
        ):
            targets.append(candidate)
            seen.add(candidate.node_id)
    if node.node_id not in seen:
        targets.append(node)
    return targets


def append_output_line(canvas, node: WorkflowNode, line: str) -> None:
    """Append one plain line to a node log (LLM nodes receive it as a note)."""
    if isinstance(node, LLMNode):
        add_llm_note(canvas, node, line, LEVEL_INFO)
        return
    for target in iter_output_targets(canvas, node):
        target.append_output(line)
        if canvas.on_output_line:
            canvas.on_output_line(target, line)


def clear_node_output(canvas, node: WorkflowNode) -> None:
    for target in iter_output_targets(canvas, node):
        target.clear_output()
        if canvas.on_output_cleared and not isinstance(target, LLMNode):
            canvas.on_output_cleared(target)


# ----------------------------------------------------------------------
# LLM transcript operations
# ----------------------------------------------------------------------


def _apply_to_transcripts(canvas, node: LLMNode, operation: Callable[[ChatTranscript], None]) -> None:
    for target in iter_output_targets(canvas, node):
        if isinstance(target, LLMNode):
            operation(target.transcript)


def add_llm_note(canvas, node: LLMNode, text: str, level: str = LEVEL_INFO) -> None:
    _apply_to_transcripts(canvas, node, lambda transcript: transcript.add_diagnostic(text, level))


def start_llm_turn(canvas, node: LLMNode, composed_prompt: str, turn_id: str) -> None:
    """Add the user bubble for the prompt the workflow is about to send."""
    sender = node.title if llm_shared_session_name(node) else ""
    _apply_to_transcripts(
        canvas,
        node,
        lambda transcript: transcript.add_user_turn(composed_prompt, turn_id=turn_id, sender=sender),
    )


def apply_llm_stream_event(canvas, node: LLMNode, event: StreamEvent) -> None:
    _apply_to_transcripts(canvas, node, lambda transcript: transcript.apply_event(event))


def finish_llm_turn(
    canvas,
    node: LLMNode,
    turn_id: str,
    status: str = TURN_COMPLETED,
    error: str = "",
    final_text: str = "",
) -> None:
    """Close the turn; add the final response when nothing streamed for it."""

    def operation(transcript: ChatTranscript) -> None:
        if status == TURN_COMPLETED and final_text.strip() and not transcript.turn_has_assistant_text(turn_id):
            transcript.add_assistant(final_text)
        transcript.finish_turn(turn_id, status, error)

    _apply_to_transcripts(canvas, node, operation)


def interrupt_all_llm_turns(canvas) -> None:
    for node in canvas._nodes.values():
        if isinstance(node, LLMNode):
            node.transcript.interrupt_open_turns()


def llm_history_kept_on_run(canvas, node: LLMNode) -> bool:
    """Whether a run continues this node's conversation instead of restarting it.

    History is kept when the next call will resume an existing CLI session:
    a named session that already has a captured id (and whose owner is not
    restarting), or node-local resume with a saved id.
    """
    provider = get_provider_for_model(node.model_id or "")
    if provider is None or not provider.supports_session_resume(node.model_id):
        return False
    shared = llm_shared_session_name(node)
    if shared:
        record = canvas._named_sessions.get(shared)
        if record is None or not record.get("session_id", "").strip():
            return False
        owner = canvas._nodes.get(record.get("owner_node_id", ""))
        if isinstance(owner, LLMNode) and owner.restart_session_enabled and owner.save_session_enabled:
            return False
        return True
    return bool(node.resume_session_enabled and node.saved_session_id.strip())
