# assets Developer Guide

## Purpose
`src/gui/assets/` stores provider image assets used by Qt graph item rendering.

## Contents
- `claude_logo.png`: Anthropic/Claude logo.
- `openai_logo.png`: OpenAI/Codex logo.

## Usage
- `src/gui/llm_widget.py` loads these files through `QIcon` for provider artwork on graph items.
- Icons are normalized to a fixed 16x16 canvas while preserving aspect ratio, so source images can have different dimensions.
- Keep file names stable because icon lookup is path-based.
- Providers without a logo file (Grok, OpenCode) get a generated rounded-rect fallback icon from `_fallback_provider_icon` in `llm_widget.py`; add a PNG plus a `PROVIDER_LOGO_FILES` entry to replace one.
