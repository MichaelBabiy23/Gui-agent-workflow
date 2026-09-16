# Desktop Editor Developer Guide

## Purpose
`desktop/` is the visible Electron shell for GUI Workflow. The renderer is a React graph editor. Electron starts one local Python bridge process and relays structured messages; the bridge owns workflow execution and JSON files.

## Files
- `main.cjs`: Creates the window, starts the bridge, handles file and folder dialogs, and relays messages.
- `preload.cjs`: Exposes a narrow request and event API to the renderer.
- `package.json`, `vite.config.js`, `index.html`: Build and launch configuration.
- `src/`: React editor components, dialogs, connection editing, and styles. Read `src/src_developer_guide.md` before changing it.

## Launch
Run `npm install` once in this folder, then `npm run dev` for the live editor. `npm run build` and `npm start` launch the built editor. `run_gui_workflow.bat` performs the build when needed.

## Security
The renderer has no Node access. Only the preload API reaches Electron. Python communicates over standard input and output, with no network listener. Electron blocks renderer navigation and only opens HTTP or HTTPS links externally.
