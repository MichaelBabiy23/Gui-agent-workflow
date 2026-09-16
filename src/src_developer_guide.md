# src Developer Guide

## Purpose
`src/` is the runtime package for GUI Workflow. It contains all app code grouped by UI, provider integration, and background execution.

## Folder Map
- `gui/`: Qt graphics-based workflow editor and main-window shell.
- `llm/`: Provider abstraction and concrete CLI adapters (Claude, Codex, Grok, OpenCode).
- `workers/`: Threaded subprocess workers used to execute LLM, git, and script commands without blocking UI.

## Data Flow
1. UI collects node configuration through `PropertiesPanel`. The panel stays visible at all times: with one selected node it shows node-edit forms, with one selected connection it shows arrow details plus connection-edit shortcuts, otherwise it shows a workflow overview summary. Content fields commit directly to node attributes, while title, model, resume-session toggle, op-type, condition-type, loop-count, join-count, and git-action changes go through canvas undo handlers.
2. `WorkflowCanvas` in `src/gui/canvas/` handles graph interaction, connection routing, clipboard, undo/redo, and save/load. It supports LLM, file-op, conditional, attention, loop, join, git-action, and script-runner nodes. Manual connection vertices are serialized in each connection record as `vertices` and restored through load, undo, and paste flows.
3. Canvas offers three run modes: Run All, Run Selected, and Run From Here. Pre-run validation requires prompt plus resolvable model for `LLMNode`; filename for `FileOpNode`; known `condition_type` and a filename only for filename-scoped conditions on `ConditionalNode`; non-empty message for `AttentionNode`; valid git enums plus commit-message requirements for `GitActionNode`; and a selected `.bat`, `.cmd`, or `.ps1` path for `ScriptNode`.
4. `LLMNode` execution uses `LLMWorker` in a background `QThread`. Prompt text is assembled through `src.llm.prompt_injection.compose_prompt(...)` using the active global template selection plus each node's saved prepend/append override state. Claude, Codex, Grok, and OpenCode providers use structured CLI output so the worker can capture resumable conversation IDs (`session_id` for Claude/Grok/OpenCode, `thread_id` for Codex). While the subprocess runs, structured providers translate their JSON lines into provider-neutral `StreamEvent`s (`llm/stream_events.py`) that the GUI folds into the LLM node's chat transcript (`gui/llm_chat/`), so tool calls and intermediate replies appear live before the final response is parsed.
5. LLM session state is split between per-node fields on `LLMNode` (`resume_session_enabled`, `save_session_enabled`, `save_session_name`, `restart_session_enabled`, `resume_named_session_name`, `saved_session_id`, `saved_session_provider`) and a workflow-level named-session store on `WorkflowCanvas`. If a loaded workflow contains saved node or named sessions, `MainWindow` asks on the next run whether to resume them or clear them and start fresh.
6. Saved workflows that reference retired model IDs are normalized onto the current provider catalog during load and provider lookup. Claude carries explicit aliases for older saved IDs so existing graphs continue to validate and run.
7. When `resume_session_enabled` is checked on a resumable LLM node (Claude, Codex, Grok, OpenCode), later calls reuse that node's saved session ID. Named-session resume pulls from the workflow-level store instead, but only when the target session already has a captured ID, matches the current provider, and the graph contains a directed path from the save-owner node to the current load node. A save-owner node can also persist `restart_session_enabled`, which makes that node ignore the currently saved resumable ID for its own call and overwrite the workflow-named session only after the fresh call finishes.
8. Canvas execution serializes concurrent invocations that reuse the same resumable conversation, whether the reuse key is the node-local previous session or a workflow-level named session.
9. Copy/paste always produces a fresh LLM node session state. Pasted nodes keep `resume_session_enabled`, but named-session save/resume bindings and captured provider session IDs are cleared.

## Current Built-In Models
- Claude provider: Fable 5.1 (efforts low/medium/high/xhigh/max, default high), Opus 5 (same ladder, default high), and Sonnet 5 (same ladder, default medium).
- Codex CLI / OpenAI provider: GPT-6 Astra (default medium, efforts through max), GPT-5.6 Sol (default low), Terra (default medium), and Luna (default medium); Sol/Terra offer efforts through ultra, Luna through max.
- Grok provider: Grok 4.6 (low/medium/high/xhigh) and Grok 4.5 (low/medium/high).
- OpenCode provider: free OpenCode Zen models (Big Pickle, MiMo-V2.5 Free, Ling 3.0 Flash Fin Free, Nemotron 3 Ultra Free, Nemotron 3.5 Lightning Free, Muse Spark 1.3 Contributor Free) without effort variants.

Model selection is two-stage in the UI: one dropdown row per model, then an Effort dropdown populated from the chosen entry's variants; nodes store `<model>:<variant>` composed ids.

## When To Edit What
- Graph interaction and serialization behavior: `gui/`.
- UI shell behavior, save/load prompts, and panel flows: `gui/main_window.py` plus `gui/properties_panel.py`.
- Add or adjust model catalogs and CLI flags: `llm/`.
- Change prompt template storage, prompt assembly order, or built-in runtime context text: `llm/prompt_injection.py`.
- Process execution, cancellation, timeout handling, or structured result capture: `workers/`.
