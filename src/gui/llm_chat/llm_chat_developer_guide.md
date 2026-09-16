# Conversation Model Developer Guide

## Purpose

`llm_chat/` holds provider-neutral in-memory conversation data for LLM nodes. The Electron inspector renders these records as chat tabs. A node can own several real CLI conversations; only a call that resumes a captured provider session ID continues an existing one.

## Files

- `transcript.py`: `ChatItem` and `ChatTranscript`. A transcript has an ordered item list, a canvas conversation ID, an optional provider session ID, and change listeners. It accepts `StreamEvent` values and tracks user turns, assistant replies, tool activity, and diagnostics.
- `conversations.py`: `ChatConversations`, an ordered collection of transcripts with add, reset, changed, and turn-start notifications. It finds conversations by ID or captured provider session ID.
- `__init__.py`: Re-exports the models and turn-status constants used by canvas execution.

## Data Flow

1. The canvas chooses a conversation based on the session ID the provider call will resume. A new provider session opens a new transcript.
2. `LLMWorker` emits provider-neutral stream events. Canvas callbacks fold them into transcript items on the Qt event loop.
3. On completion, the captured session ID is attached to the transcript and the turn is marked completed, failed, or interrupted.
4. The bridge serializes transcript items into state snapshots. React displays the selected node's conversations in Output.

Shared workflow-named sessions apply the same operations to participating nodes with the same conversation ID. Keep provider-specific JSON parsing in `src/llm/` and worker code.
