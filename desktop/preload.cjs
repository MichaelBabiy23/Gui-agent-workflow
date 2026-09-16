const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("workflow", {
  request: (action, payload = {}) =>
    ipcRenderer.invoke("bridge:request", action, payload),
  dialog: (kind, options = {}) =>
    ipcRenderer.invoke("bridge:dialog", kind, options),
  openExternal: (url) => ipcRenderer.invoke("bridge:open-external", url),
  onMessage: (listener) => {
    const handler = (_event, message) => listener(message);
    ipcRenderer.on("bridge:message", handler);
    return () => ipcRenderer.removeListener("bridge:message", handler);
  },
});
