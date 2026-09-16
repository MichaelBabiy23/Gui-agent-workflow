# GUI Workflow

A desktop studio for visual LLM workflows. Connect nodes, configure their work, and watch runs unfold live.

![GUI Workflow desktop editor](screen%20shot/screenshot%201.png)

## Get started

On Windows, run `run_gui_workflow.bat`. The launcher installs missing Python dependencies and desktop packages, builds the editor, and opens the app. You need Python 3.11 or newer, Node.js with npm, and any provider CLIs you plan to use.

You can also run `python workflow_entry.py`. For editor development, run `npm run dev` in `desktop/` after `npm install`.

Choose a project folder before running a workflow. Provider, git, and script commands run in that folder.

## Build a workflow

Use the node library to add LLM calls, file operations, variables, conditions, loops, joins, git actions, scripts, and attention prompts. Drag from an output port to an input port to connect steps. Select a node to edit its settings in the inspector. Run All begins at Start; Run Selected runs only selected nodes; Run From Here runs a selected node and its descendants.

The canvas supports panning, zooming, multi-selection, connection bend points, undo and redo, and copy and paste. Double-click a connection to add a bend point. Drag a selected point to move it; Shift-click it to remove it.

## Save and run

Open and save workflow JSON files from the title bar. Existing workflow JSON files open in the desktop editor with their nodes, connections, manual bends, model settings, prompt-template overrides, and session metadata. Saved CLI sessions can resume on the next run or start fresh.

LLM output appears as conversation tabs in the inspector. Prompts, assistant messages, tool activity, and diagnostics update during a run. Other nodes show a text log. Attention nodes ask whether their branch should continue. Provider usage-limit errors offer a model change or scheduled resume.

Prompt templates and one-time context are available from the menu in the title bar. Templates can be set as defaults or selected per LLM node. Claude and Codex nodes can choose a discovered account profile.

## Structure

- `desktop/`: Electron window and React Flow editor.
- `src/bridge/`: Local message bridge between the editor and runtime.
- `src/gui/`: Graph objects, workflow validation, execution, and JSON handling.
- `src/llm/`: Provider CLIs, model catalogs, profiles, and prompt templates.
- `src/workers/`: Background subprocess workers.

See [gui_workflow_developer_guide.md](gui_workflow_developer_guide.md) for architecture and development checks.
