# Editor Source Developer Guide

## Purpose

React renders the workflow graph, inspector, and controls. Python remains the source of truth for saved workflow data and execution state.

## Files

- `main.jsx`: React entry point.
- `App.jsx`: Main shell, graph state, editing actions, file actions, run controls, and keyboard shortcuts.
- `GraphNode.jsx`: Compact node cards and port handles.
- `Inspector.jsx`: Node settings and output views. It loads assistant Markdown rendering when an output view needs it.
- `MarkdownMessage.jsx`: GitHub-style Markdown rendering for assistant text. Links pass through the Electron external-link validator.
- `Dialogs.jsx`: Attention, saved-session, usage-limit, and prompt-template dialogs.
- `WorkflowEdge.jsx`: Connection paths and editable bend points.
- `styles.css`: Dark desktop theme, shell layout, canvas controls, and node appearance.
- `inspector.css`: Inspector, chat, modal, and responsive appearance.

## State Flow

`window.workflow.onMessage` delivers bridge snapshots. React Flow applies local drag changes immediately and sends positions when a drag stops. Other edits are sent through `window.workflow.request`. The inspector keeps text drafts until blur to avoid replacing the user's active text during streamed run updates.

## Workflow Files

Never construct saved workflow JSON in the renderer. Use bridge load/save actions so the existing parser, node defaults, and session data stay authoritative.
