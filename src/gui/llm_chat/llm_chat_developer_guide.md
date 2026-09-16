# llm_chat Developer Guide

## Purpose
Renders an LLM node's conversation as a chat: the prompts the workflow sent (user bubbles), what the model did while working (collapsible tool-activity rows), what it answered (markdown), and diagnostics. The design reproduces the Skylyx Hub code-tab chat with native Qt widgets: same palette, type sizes, icons, layout, and behaviors (working shimmer, jump-to-latest, hover rows, rotating chevrons).

## Files
- `transcript.py`: `ChatItem` and `ChatTranscript`. The transcript is the provider-neutral data model: an ordered item list plus change listeners (`append`, `update`, `reset`). It folds `StreamEvent` objects from `src/llm/stream_events.py` into items (`apply_event`), opens user turns (`add_user_turn` with a caller-supplied `turn_id`), and closes them (`finish_turn` with `completed`, `failed`, or `interrupted`, which also marks still-running tool rows). `busy` is true while any turn is open.
- `theme.py`: Resolved Skylyx design tokens (background `#181c22`, text `#cccfd7`, accent `#22d3ee`, and the `color-mix()` results for muted, line, bubble, activity, and live-pill colors), font builders (`ui_font`, `code_font`), column sizing, and the SVG icon bodies used for activity kinds, crumbs, and chevrons.
- `common_widgets.py`: `svg_pixmap`/`IconLabel`/`ChevronLabel` (SVG icons via QtSvg), `ShineLabel` (text with the moving highlight sweep used for "Working for" and running tool titles), `ElidedLabel`, `PreBox` (read-only monospace block that grows to a 320 px cap), and `SegmentedToggle` (the `.segmented` control).
- `markdown_view.py`: `MarkdownView`, a frameless auto-growing `QTextBrowser`. It imports GitHub markdown, moves fenced code into padded bordered frames, styles inline code, headings, quotes, and links, and sizes itself to its text width (`setFixedHeight` on resize plus `heightForWidth`). Ctrl+wheel is ignored so the panel zoom filter receives it.
- `activity_widget.py`: `ActivityWidget`, the `details`-style row. `classify()` maps an item to a kind (`command`, `edit`, `read`, `thinking`, `search`, `diagnostic`, `tool`), a title ("Ran command", "Edited file", "Read file", "Changed files", the tool name, or the diagnostic level), and a monospace detail. The expandable body shows Command, working directory, script/file contents, changed files, an old/new edit preview, Input, Output, and exit code.
- `message_widgets.py`: `UserTurnWidget` (optional sender caption, right-aligned bubble capped at 80% width, working row that reads "Working for Ns" while open or "Worked for" / "Failed after" / "Stopped after" once closed, and the red error line), `AssistantWidget`, and `EmptyStateWidget`.
- `chat_view.py`: `ChatHeader` (crumb with folder icon for the session label, `/`, node title, pulsing `Working` pill, Settings/Output toggle) and `ChatView` (scrolling centered column of item widgets bound to one transcript). `ChatView` follows new output unless the user scrolled up more than 80 px, in which case a `↓ Latest` pill appears; a 1 s ticker refreshes elapsed times; `turn_started` fires only for live user turns so the form can switch to Output automatically.
- `__init__.py`: Re-exports the view classes, the transcript types, and the turn status constants.

## Data Flow
1. `WorkflowCanvas._fire_invocation` creates a `turn_id`, calls `start_llm_turn` (user bubble), and starts `LLMWorker`.
2. `LLMWorker.stream_event` delivers `StreamEvent`s; the canvas applies them to every mirrored transcript (`apply_llm_stream_event`).
3. On completion the canvas calls `finish_llm_turn`; when nothing streamed for that turn, the parsed final response is added as the assistant item first.
4. `_LLMForm.bind_transcript` subscribes the single `ChatView` to the selected node's transcript. Each node keeps its own `ChatTranscript` object; shared workflow sessions receive identical operations, so switching between those nodes shows the same conversation.

## Conventions
- Widgets take a `scale` (1.0 = the Skylyx pixel sizes) and expose `set_text_scale`; the panel maps its integer zoom onto that scale and rebuilds the column.
- Never create or mutate chat widgets from a worker thread; all transcript mutations happen in canvas slots on the GUI thread.
- Keep provider JSON knowledge out of this package; extend `StreamEvent` and the provider parsers instead.
