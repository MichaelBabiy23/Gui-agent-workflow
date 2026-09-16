const { app, BrowserWindow, dialog, ipcMain, shell } = require("electron");
const { spawn } = require("node:child_process");
const path = require("node:path");
const readline = require("node:readline");

const projectRoot = path.resolve(__dirname, "..");
const prefix = "@@GUI@@";
let window;
let backend;
let nextId = 1;
let shuttingDown = false;
const pending = new Map();
let latestState = null;

function publish(message) {
  if (message.type === "state") latestState = message.state;
  if (window && !window.isDestroyed())
    window.webContents.send("bridge:message", message);
}

function failPending(reason) {
  for (const { reject } of pending.values()) reject(new Error(reason));
  pending.clear();
}

function startBackend() {
  const preferred =
    process.env.GUI_WORKFLOW_PYTHON ||
    (process.platform === "win32" ? "py" : "python3");
  const args =
    process.platform === "win32" && !process.env.GUI_WORKFLOW_PYTHON
      ? ["-3", "-m", "src.bridge.server"]
      : ["-m", "src.bridge.server"];
  backend = spawn(preferred, args, {
    cwd: projectRoot,
    env: {
      ...process.env,
      QT_QPA_PLATFORM: "offscreen",
      PYTHONUNBUFFERED: "1",
    },
    stdio: ["pipe", "pipe", "pipe"],
    windowsHide: true,
  });
  backend.on("error", (error) => {
    publish({
      type: "error",
      error: `Could not start Python: ${error.message}`,
    });
    failPending(error.message);
  });
  backend.on("exit", (code) => {
    if (!shuttingDown)
      publish({ type: "error", error: `Workflow runtime exited (${code}).` });
    failPending("Workflow runtime stopped.");
  });
  backend.stderr.on("data", (chunk) => process.stderr.write(chunk));
  readline.createInterface({ input: backend.stdout }).on("line", (line) => {
    if (!line.startsWith(prefix)) return;
    let message;
    try {
      message = JSON.parse(line.slice(prefix.length));
    } catch {
      return;
    }
    if (message.id !== undefined) {
      const item = pending.get(message.id);
      if (!item) return;
      pending.delete(message.id);
      if (message.ok) item.resolve(message.result);
      else item.reject(new Error(message.error || "Runtime request failed."));
    } else publish(message);
  });
}

function request(action, payload = {}) {
  if (!backend || !backend.stdin.writable)
    return Promise.reject(new Error("Workflow runtime is unavailable."));
  const id = nextId++;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    backend.stdin.write(JSON.stringify({ id, action, payload }) + "\n");
  });
}

async function choose(kind, options) {
  if (kind === "project") {
    const result = await dialog.showOpenDialog(window, {
      properties: ["openDirectory"],
    });
    return result.canceled ? null : result.filePaths[0];
  }
  if (kind === "load") {
    const result = await dialog.showOpenDialog(window, {
      properties: ["openFile"],
      filters: [{ name: "Workflow JSON", extensions: ["json"] }],
    });
    return result.canceled ? null : result.filePaths[0];
  }
  if (kind === "save") {
    const result = await dialog.showSaveDialog(window, {
      defaultPath: options.current || "workflow.json",
      filters: [{ name: "Workflow JSON", extensions: ["json"] }],
    });
    return result.canceled ? null : result.filePath;
  }
  if (kind === "script") {
    const result = await dialog.showOpenDialog(window, {
      properties: ["openFile"],
      defaultPath: options.project || projectRoot,
      filters: [{ name: "Scripts", extensions: ["bat", "cmd", "ps1"] }],
    });
    return result.canceled ? null : result.filePaths[0];
  }
  throw new Error(`Unknown dialog: ${kind}`);
}

app.whenReady().then(() => {
  ipcMain.handle("bridge:request", (_event, action, payload) => {
    if (action === "state" && latestState) return latestState;
    return request(action, payload);
  });
  ipcMain.handle("bridge:dialog", (_event, kind, options) =>
    choose(kind, options),
  );
  ipcMain.handle("bridge:open-external", (_event, rawUrl) => {
    const url = new URL(rawUrl);
    if (!["https:", "http:"].includes(url.protocol))
      throw new Error("Only web links can open outside the app.");
    return shell.openExternal(url.toString());
  });
  startBackend();
  window = new BrowserWindow({
    width: 1600,
    height: 980,
    minWidth: 1060,
    minHeight: 680,
    backgroundColor: "#0b0d12",
    title: "GUI Workflow",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  window.on("close", (event) => {
    if (!latestState?.dirty) return;
    const answer = dialog.showMessageBoxSync(window, {
      type: "warning",
      buttons: ["Keep editing", "Discard changes"],
      defaultId: 0,
      cancelId: 0,
      title: "Unsaved workflow",
      message: "Discard unsaved workflow changes?",
    });
    if (answer === 0) event.preventDefault();
  });
  window.webContents.on("will-navigate", (event) => event.preventDefault());
  window.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  if (process.env.VITE_DEV_SERVER_URL)
    window.loadURL(process.env.VITE_DEV_SERVER_URL);
  else if (process.env.npm_lifecycle_event === "dev")
    window.loadURL("http://127.0.0.1:5173");
  else window.loadFile(path.join(__dirname, "dist", "index.html"));
});

app.on("window-all-closed", () => {
  if (!backend || backend.exitCode !== null) {
    app.quit();
    return;
  }
  shuttingDown = true;
  const timeout = setTimeout(() => backend.kill(), 5000);
  backend.once("exit", () => {
    clearTimeout(timeout);
    app.quit();
  });
  request("quit").catch(() => backend.kill());
});
