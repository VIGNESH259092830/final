const { contextBridge, ipcRenderer } = require('electron');

// API for backend communication
contextBridge.exposeInMainWorld('api', {
    askAI: (text) => fetch('http://127.0.0.1:8000/answer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
    }),
    toggleMic: () => fetch('http://127.0.0.1:8000/toggle-mic', { method: 'POST' }),
    toggleSystem: () => fetch('http://127.0.0.1:8000/toggle-system', { method: 'POST' })
});

// Electron API for window controls and IPC
contextBridge.exposeInMainWorld('electronAPI', {
    minimizeWindow: () => ipcRenderer.send('minimize-window'),
    closeWindow: () => ipcRenderer.send('close-window'),
    restoreWindow: () => ipcRenderer.send('restore-window'),
    moveCircle: (x, y) => ipcRenderer.send('move-circle', x, y),
    dragWindow: (deltaX, deltaY) => ipcRenderer.send('drag-window', deltaX, deltaY),
    toggleIgnoreMouse: (ignore) => ipcRenderer.send('toggle-ignore-mouse', ignore),
    moveOverlay: (direction) => ipcRenderer.send('move-overlay', direction),
    
    // 🔥 CLICK-THROUGH OVERLAY APIs
    toggleClickThrough: (ignore) => ipcRenderer.send('toggle-click-through', ignore),
    checkInteractiveArea: (x, y) => ipcRenderer.send('check-interactive-area', x, y),
    reportHitTest: (isInteractive) => ipcRenderer.send('hit-test-result', isInteractive),
    
    // 🔥 GLOBAL HOTKEY LISTENER
    onGlobalHotkey: (callback) => {
        ipcRenderer.on('global-hotkey', (event, data) => callback(data));
    },
    
    // 🔥 Listen for hit-test requests from main process
    onHitTestRequest: (callback) => ipcRenderer.on('request-hit-test', (event, data) => callback(data)),
    
    // 🔥 Additional click-through handlers
    mouseEnterClickable: () => ipcRenderer.send('mouse-enter-clickable'),
    mouseLeaveClickable: () => ipcRenderer.send('mouse-leave-clickable')
});