// preload.js - Complete API
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    /* Window */
    minimizeWindow: () => ipcRenderer.send('minimize-window'),
    closeWindow: () => ipcRenderer.send('close-window'),
    restoreWindow: () => ipcRenderer.send('restore-window'),
    toggleClickThrough: (ignore) => ipcRenderer.send('toggle-click-through', ignore),

    /* Screenshot */
    takeScreenshot: (region) => ipcRenderer.send('take-screenshot', region),
    captureForChat: () => ipcRenderer.send('capture-for-chat'),
    toggleAutoAnswer: () => ipcRenderer.send('toggle-auto-answer'),
    getLastScreenshot: () => ipcRenderer.invoke('get-last-screenshot'),
    getScreenshotHistory: () => ipcRenderer.invoke('get-screenshot-history'),
    clearScreenshotHistory: () => ipcRenderer.send('clear-screenshot-history'),

    /* Screenshot events */
    onScreenshotProcessing: (cb) => ipcRenderer.on('screenshot-processing', (e, d) => cb(d)),
    onScreenshotResult: (cb) => ipcRenderer.on('screenshot-result', (e, d) => cb(d)),
    onScreenshotError: (cb) => ipcRenderer.on('screenshot-error', (e, d) => cb(d)),
    onScreenshotTranscript: (cb) => ipcRenderer.on('screenshot-transcript', (e, d) => cb(d)),
    onScreenshotCaptured: (cb) => ipcRenderer.on('screenshot-captured', (e, d) => cb(d)),
    onAutoAnswerToggled: (cb) => ipcRenderer.on('auto-answer-toggled', (e, d) => cb(d)),
    onShowLastScreenshot: (cb) => ipcRenderer.on('show-last-screenshot', () => cb()),

    /* Global hotkey */
    onGlobalHotkey: (cb) => ipcRenderer.on('global-hotkey', (e, d) => cb(d)),

    /* Circle window */
    moveCircle: (x, y) => ipcRenderer.send('move-circle', x, y),
});