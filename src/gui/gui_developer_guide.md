# Graph And Execution Developer Guide

## Purpose

`src/gui/` holds the Qt graph objects and workflow behavior used by the Python runtime. The Electron editor talks to these objects through `src/bridge/server.py`; it does not construct Qt widgets in the visible window.

## Active Runtime Map

- `canvas/`: `WorkflowCanvas`, graph mutations, execution, validation, sessions, variables, and subprocess coordination.
- `workflow_io.py`: Workflow JSON parsing, validation, and serialization helpers.
- `llm_node.py`: Base graph item, permanent Start node, LLM node state, and visual status fields.
- `file_op_node.py`, `conditional_node.py`, `loop_node.py`, `git_action_node.py`, `control_flow/`, `script_runner/`, `variables/`: Built-in graph item types.
- `connection_item.py`: Directed connections, source ports, and manual bend points.
- `undo_commands.py`: Qt command implementations used by canvas graph methods. The desktop bridge also keeps whole-graph snapshots for editor undo and redo.
- `llm_chat/`: Conversation and transcript models fed by provider stream events.
- `llm_sessions/`: Named-session filtering, ownership, and sharing rules.
- `llm_widget.py`: Shared model lookup and provider icon helpers used by graph items.

## Graph Rules

Start is permanent. Run All validates all reachable nodes and starts its direct children. Run Selected starts selected nodes without downstream fan-out. Run From Here starts one node and its descendants. Condition and loop nodes expose named source ports; all other source nodes use `output`.

Node validation drives both run blocking and `is_invalid` status shown by the editor. `WorkflowCanvas.load_workflow_data()` restores nodes, connections, manual vertices, and workflow-named sessions. `get_workflow_data()` produces the same JSON shape for saving.

LLM nodes store their model, prompt, profile, per-node prompt-template overrides, and resumable session metadata. The execution engine composes variable substitutions and prompt injections, then calls the provider in `LLMWorker`. Structured provider events update conversation models while calls run. Calls sharing a resumed CLI session are serialized.

The selected project folder is set through `WorkflowCanvas.set_working_directory()`. File operations, scripts, git actions, and provider calls use that folder. The canvas confines project-relative file and script paths before execution.

## Attention And Output

An attention node blocks only its own branch while awaiting a decision. The canvas calls `on_attention_requested` when the bridge supplies it, allowing the Electron dialog to answer through the protocol. Other branches and workers continue in the Qt event loop.

Non-LLM nodes keep plain-text output. LLM nodes keep one transcript per real provider conversation, including prompt, assistant, tool, and diagnostic items. Named-session participants share the same conversation history.

Read the folder-specific guide before editing a subpackage.
