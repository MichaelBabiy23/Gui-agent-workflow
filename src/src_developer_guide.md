# Runtime Package Developer Guide

## Purpose

`src/` contains the Python workflow runtime. Electron starts `src.bridge.server` as a child process. The bridge operates the graph on the Qt event loop, publishes JSON state to the React editor, and leaves provider subprocesses in background workers.

## Folder Map

- `bridge/`: Local standard-input and standard-output protocol for the desktop editor.
- `gui/`: Qt graph objects, workflow serialization, validation, sessions, prompt preview, and execution.
- `llm/`: Provider registry and CLI adapters, model catalogs, profiles, and prompt injection.
- `workers/`: Subprocess workers with output streaming, cancellation, and timeouts.
- `platform_power/`: Windows sleep prevention while workflows run.

## Data Flow

1. The desktop editor requests graph actions and file operations through the bridge. The reader thread queues requests, and Qt timer callbacks handle them on the graph's owning thread.
2. `WorkflowCanvas` stores nodes, connections, working directory, named sessions, variables, and run state. Its workflow JSON parser and serializer are the only file-format authority.
3. The bridge publishes graph, validation, output, and conversation snapshots. React Flow keeps immediate drag feedback locally and commits completed moves to the graph.
4. The execution engine validates reachable nodes, fans out from Start, and routes conditional and loop ports. LLM, git, and script nodes run in workers. File, variable, attention, loop, and join behavior is coordinated on the Qt event loop.
5. Provider-neutral `StreamEvent` objects update the chat transcript during LLM calls. Captured session IDs live on nodes and in workflow-named session records.

## Key Invariants

- The bridge never mutates canvas objects from its input reader thread.
- Workflow JSON is loaded and saved through the canvas so every node field, named session, and manual connection bend survives round trips.
- Project-relative file and script paths are checked by canvas execution helpers.
- A run validates nodes before starting and prevents graph edits until it ends.
- Attention responses return through the bridge to the waiting execution branch.

Read the local guide in each folder before editing code there.
