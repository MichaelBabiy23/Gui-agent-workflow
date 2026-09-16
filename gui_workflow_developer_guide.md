# GUI Workflow Developer Guide

## Purpose

GUI Workflow is a Windows desktop application for composing and running node-based LLM workflows. Electron hosts a React and React Flow editor. A local Python process owns graph serialization, validation, provider calls, and execution.

## Top-Level Map

- `workflow_entry.py`: Main launcher. Installs desktop packages when needed, builds the editor when needed, and starts Electron with the selected Python interpreter for the runtime.
- `run_gui_workflow.bat`: Windows launcher. Ensures Python and PySide6 are available, then calls `workflow_entry.py`.
- `desktop/`: Electron shell and React editor. Read `desktop/desktop_developer_guide.md` before editing.
- `src/bridge/`: JSON message adapter between Electron and the Python workflow engine. Read its guide before editing.
- `src/gui/`: Graph objects, workflow execution, validation, sessions, and serialization. The bridge creates a Qt application with the offscreen platform plugin so these objects and worker signals can run without a Qt window.
- `src/llm/`: Provider catalogs, CLI commands, output parsing, profiles, and prompt templates.
- `src/workers/`: Background subprocess workers.
- `saves/`: Workflow JSON fixtures.
- `requirements.txt`: Python runtime dependencies.

## Runtime Flow

1. The launcher starts Electron. Electron starts `python -m src.bridge.server` as one child process and loads the built React editor.
2. The renderer calls the narrow preload API. Electron relays requests to Python over standard input and responses and state events over standard output. Only lines beginning with `@@GUI@@` are protocol messages.
3. The bridge creates `WorkflowCanvas` inside a hidden Qt application. All canvas actions run on the Qt event loop. A reader thread queues requests, and a timer drains that queue and publishes changed state.
4. React Flow handles immediate canvas interaction. It commits completed node moves, connections, property edits, and bend-point edits to the bridge. The bridge owns the authoritative graph and its undo snapshots.
5. Load and save call `WorkflowCanvas.load_workflow_data()` and `get_workflow_data()`. Existing workflow JSON files use the same parser and serializer as runtime execution. Node and named-session fields remain in the workflow file.
6. Run All, Run Selected, and Run From Here validate nodes through the canvas and call its execution engine. The bridge streams status, node output, conversations, and usage-limit events to the editor. Attention nodes wait for an explicit response from the desktop dialog.
7. LLM calls use provider CLIs in background workers. Prompt templates and account profiles are resolved by `src/llm/` and applied by the canvas.

## Workflow Graph

The permanent Start node triggers direct children in Run All. Available node types are LLM, file operation, conditional, attention, loop, join, git action, script, and variable. Conditional and loop nodes use named source ports. Connections can carry manual `vertices` in workflow JSON. The editor shows validation state on each node and the selected node's settings or output in the inspector.

The selected project folder is the working directory for provider, git, and script subprocesses. File and script operations validate project-relative paths. Workflow files can be saved anywhere.

## Provider And Session State

Claude, Codex, Grok, and OpenCode use CLI adapters under `src/llm/`. Installed provider CLIs populate the model catalog. Claude and Codex can use named local account profiles. LLM nodes can resume their own provider session or a reachable workflow-named session. The runtime serializes calls that share a resumable session. The inspector shows each real CLI conversation in a separate chat tab.

Prompt templates and global defaults are saved in `.prompt_injections.json`. Workflow JSON stores per-node template overrides. A one-time prompt addition can be placed before or after the node prompt for the next run.

## Developer Checks

- Python syntax: `py -3 -m compileall -q workflow_entry.py src`
- Desktop lint: `cd desktop && npm run lint`
- Desktop build: `cd desktop && npm run build`
- Runtime sanity: start the bridge and load a tracked workflow JSON fixture through its protocol.

Keep generated `desktop/node_modules/`, `desktop/dist/`, and system temp files out of git. Code files must stay below 1000 lines, and each folder must have one developer guide with no more than 500 lines.
