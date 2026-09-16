# Variable Node Developer Guide

## Purpose

`variables/` defines workflow variables used by downstream LLM prompts. The desktop inspector edits the serialized fields, and canvas runtime carries values per execution lineage.

## Files

- `variable_node.py`: `VariableNode` graphics item, JSON fields, and validation helpers.
- `__init__.py`: Exports the node and helper functions.

## Rules

- Variable names use Python identifier syntax and reject keywords.
- A value is stored as the entered string. A `number` value must parse as a number before a workflow can run.
- Downstream prompt substitution follows directed graph reachability. Fan-out copies lineage variables, and joins merge them conservatively.
