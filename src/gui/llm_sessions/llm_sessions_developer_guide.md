# Named Sessions Developer Guide

## Purpose

`llm_sessions/` holds workflow-level named-session data rules. The canvas and desktop bridge use these rules to validate saved owners, provider compatibility, and reachable resume choices.

## Files

- `session_state.py`: Normalizes workflow JSON records, clones the in-memory store, checks directed paths, and reconciles session ownership and references.
- `__init__.py`: Package marker.

## Rules

- Named sessions are workflow-level records stored in workflow JSON under `named_sessions`. Each record stores a name, owner node ID, provider, and captured session ID.
- Only one LLM node may own a given name. An owner can restart its own call while other branches continue using the prior captured ID until the owner finishes.
- A node may resume a named session only when the provider matches, the owner has a directed path to that node, and a real session ID has been captured.
- Graph edits and model changes reconcile invalid references. The bridge publishes the available names to the selected node's settings.
