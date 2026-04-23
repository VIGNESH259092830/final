const { LOGO_BASE64 } = require('./logo.js');
const { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage, screen, globalShortcut } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow = null;
let circleWindow = null;
let tray = null;
let pythonServer = null;
let isMinimized = false;

/* ======================================================
   MAIN INVISIBLE WINDOW (LOCKED)
   ====================================================== */
function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1600,
        height: 600,
        minWidth: 1500,
        minHeight: 550,
        frame: false,
        transparent: true,
        backgroundColor: '#00000000',
        show: true,

        // 🔴 NEVER appear in taskbar / Alt+Tab
        skipTaskbar: true,

        // 🔥 MUST stay above all apps
        alwaysOnTop: true,

        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js')
        }
    });

    // 🔐 Invisible to screen sharing (Zoom / Teams / OBS)
    mainWindow.setContentProtection(true);

    // 🔥 Strongest Windows always-on-top level
    mainWindow.setAlwaysOnTop(true, 'screen-saver');

    mainWindow.loadFile('index.html');

    createTray();
    setupGlobalHotkeys();
    startBackend();

    /* ================= IPC ================= */

    ipcMain.on('close-window', () => app.quit());
    ipcMain.on('restore-window', restoreFromCircle);

    // Handle circle dragging with relative movement
    ipcMain.on('move-circle-relative', (event, deltaX, deltaY) => {
        if (circleWindow) {
            const [currentX, currentY] = circleWindow.getPosition();
            circleWindow.setPosition(currentX + deltaX, currentY + deltaY);
        }
    });

    // Handle step window dragging
    ipcMain.on('move-step-window', (event, deltaX, deltaY) => {
        if (mainWindow && mainWindow.isVisible()) {
            const [currentX, currentY] = mainWindow.getPosition();
            mainWindow.setPosition(currentX + deltaX, currentY + deltaY);
        }
    });

    // 🔥 CLICK-THROUGH OVERLAY - Toggle mouse events
    ipcMain.on('toggle-click-through', (event, ignoreMouseEvents) => {
        if (mainWindow) {
            mainWindow.setIgnoreMouseEvents(ignoreMouseEvents, { forward: ignoreMouseEvents });
            console.log(`🔄 Click-through toggled: ${ignoreMouseEvents ? '🔴 PASS-THROUGH' : '🟢 INTERACTIVE'}`);
        }
    });

    // 🔥 HIT-TEST - Check if position is over interactive element
    ipcMain.on('check-interactive-area', (event, x, y) => {
        if (mainWindow && mainWindow.webContents) {
            mainWindow.webContents.send('request-hit-test', { x, y });
        }
    });

    // 🔥 Response from renderer about whether element is interactive
    ipcMain.on('hit-test-result', (event, isInteractive) => {
        if (mainWindow) {
            mainWindow.setIgnoreMouseEvents(!isInteractive, { forward: !isInteractive });
            console.log(`🎯 Hit-test: ${isInteractive ? '🟢 INTERACTIVE' : '🔴 PASS-THROUGH'}`);
        }
    });

    /* ======================================================
       🔒 INVISIBILITY + FOREGROUND PROTECTION
       ====================================================== */

    // ❌ Block OS minimize (Alt+Tab / Win shortcuts)
    mainWindow.on('minimize', (e) => {
        e.preventDefault();
        if (!isMinimized) {
            mainWindow.show();
            mainWindow.setAlwaysOnTop(true, 'screen-saver');
        }
    });

    // 🔥 If focus lost (click outside / switch app)
    mainWindow.on('blur', () => {
        if (!isMinimized) {
            // Stay invisible but force front
            mainWindow.show();
            mainWindow.setAlwaysOnTop(true, 'screen-saver');
        }
        console.log('📌 Window blurred - global hotkeys remain active');
    });

    // ❌ Never allow OS hide
    mainWindow.on('hide', () => {
        if (!isMinimized) {
            mainWindow.show();
        }
    });
}

/* ======================================================
   🔥 GLOBAL HOTKEYS - WORKS EVEN WHEN MOUSE AWAY
   ====================================================== */
function setupGlobalHotkeys() {
    console.log("🌍 Registering ALL global hotkeys...");
    
    globalShortcut.unregisterAll();
    
    // ===== MODIFIER COMBINATIONS =====
    
    // Answer - Ctrl+Space
    globalShortcut.register('Control+Space', () => {
        console.log('⌨️ Global: Ctrl+Space → Answer');
        mainWindow?.webContents.send('global-hotkey', { hotkey: 'answer' });
    });
    
    // Clear - Ctrl+Shift+C
    globalShortcut.register('Control+Shift+C', () => {
        console.log('⌨️ Global: Ctrl+Shift+C → Clear');
        mainWindow?.webContents.send('global-hotkey', { hotkey: 'clear' });
    });
    
    // Chat Toggle - Ctrl+Alt+X
    globalShortcut.register('Control+Alt+X', () => {
        console.log('⌨️ Global: Ctrl+Alt+X → Chat');
        mainWindow?.webContents.send('global-hotkey', { hotkey: 'chat' });
    });
    
    // ===== SINGLE KEY TOGGLES (NO MODIFIERS) =====
    
    // 🔥 Mic Toggle - M key (no modifier) - Changed from Ctrl+M to just M
    globalShortcut.register('Control+M', () => {
    console.log('⌨️ Global: Ctrl+M → Mic Toggle');
    mainWindow?.webContents.send('global-hotkey', { hotkey: 'mic' });
});
    
    // 🔥 System Toggle - N key (no modifier) - Changed from Ctrl+N to just N
    globalShortcut.register('Control+N', () => {
    console.log('⌨️ Global: Ctrl+N → System Toggle');
    mainWindow?.webContents.send('global-hotkey', { hotkey: 'system' });
});
    
    // ===== MOVEMENT KEYS =====
    
    // Move Left - [ or Ctrl+Left
    globalShortcut.register('[', () => {
        console.log('⌨️ Global: [ → Move Left');
        mainWindow?.webContents.send('global-hotkey', { hotkey: 'move-left' });
    });
    
    globalShortcut.register('Control+Left', () => {
        console.log('⌨️ Global: Ctrl+Left → Move Left');
        mainWindow?.webContents.send('global-hotkey', { hotkey: 'move-left' });
    });
    
    // Move Right - ] or Ctrl+Right
    globalShortcut.register(']', () => {
        console.log('⌨️ Global: ] → Move Right');
        mainWindow?.webContents.send('global-hotkey', { hotkey: 'move-right' });
    });
    
    globalShortcut.register('Control+Right', () => {
        console.log('⌨️ Global: Ctrl+Right → Move Right');
        mainWindow?.webContents.send('global-hotkey', { hotkey: 'move-right' });
    });
    
    // Move Up - Ctrl+Up OR Shift+Comma (<)
    globalShortcut.register('Control+Up', () => {
        console.log('⌨️ Global: Ctrl+Up → Move Up');
        mainWindow?.webContents.send('global-hotkey', { hotkey: 'move-up' });
    });
    
    globalShortcut.register('<', () => {
        console.log('⌨️ Global: < → Move Up');
        mainWindow?.webContents.send('global-hotkey', { hotkey: 'move-up' });
    });
    
    // Move Down - Ctrl+Down OR Shift+Period (>)
    globalShortcut.register('Control+Down', () => {
        console.log('⌨️ Global: Ctrl+Down → Move Down');
        mainWindow?.webContents.send('global-hotkey', { hotkey: 'move-down' });
    });
    
    globalShortcut.register('>', () => {
        console.log('⌨️ Global: > → Move Down');
        mainWindow?.webContents.send('global-hotkey', { hotkey: 'move-down' });
    });
    
    // ===== SCROLLING KEYS =====
    
    // Scroll Down - ArrowDown
    globalShortcut.register('Down', () => {
        console.log('⌨️ Global: Down Arrow → Scroll Down');
        mainWindow?.webContents.send('global-hotkey', { hotkey: 'scroll-down' });
    });
    
    // Scroll Up - ArrowUp
    globalShortcut.register('Up', () => {
        console.log('⌨️ Global: Up Arrow → Scroll Up');
        mainWindow?.webContents.send('global-hotkey', { hotkey: 'scroll-up' });
    });
    
    // Page Down
    globalShortcut.register('PageDown', () => {
        console.log('⌨️ Global: PageDown → Scroll Page Down');
        mainWindow?.webContents.send('global-hotkey', { hotkey: 'page-down' });
    });
    
    // Page Up
    globalShortcut.register('PageUp', () => {
        console.log('⌨️ Global: PageUp → Scroll Page Up');
        mainWindow?.webContents.send('global-hotkey', { hotkey: 'page-up' });
    });
    
    console.log('✅ All global hotkeys registered');
    console.log('   📋 Hotkey Summary:');
    console.log('      Ctrl+Space     → Answer');
    console.log('      Ctrl+Shift+C   → Clear');
    console.log('      Ctrl+Alt+X     → Chat');
    console.log('      M              → Mic Toggle');
    console.log('      N              → System Toggle');
    console.log('      [ / Ctrl+Left  → Move Left');
    console.log('      ] / Ctrl+Right → Move Right');
    console.log('      < / Ctrl+Up    → Move Up');
    console.log('      > / Ctrl+Down  → Move Down');
}

/* ======================================================
   CIRCLE WINDOW (INVISIBLE)
   ====================================================== */
function createCircleWindow(x, y) {
    if (circleWindow) {
        circleWindow.focus();
        return circleWindow;
    }

    circleWindow = new BrowserWindow({
        width: 60,
        height: 60,
        x,
        y,
        frame: false,
        transparent: true,
        backgroundColor: '#00000000',

        alwaysOnTop: true,
        skipTaskbar: true,

        resizable: false,
        movable: false,
        minimizable: false,
        maximizable: false,
        fullscreenable: false,
        show: false,

        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js')
        }
    });

    circleWindow.setContentProtection(true);
    circleWindow.setAlwaysOnTop(true, 'screen-saver');

    circleWindow.loadFile('circle.html');

    circleWindow.on('closed', () => {
        circleWindow = null;
    });

    return circleWindow;
}

/* ======================================================
   MINIMIZE / RESTORE (UPDATED - TOP CENTER)
   ====================================================== */
function minimizeToCircle() {
    if (!mainWindow) return;

    isMinimized = true;
    mainWindow.hide();

    const { width } = screen.getPrimaryDisplay().workAreaSize;
    const circleX = Math.floor(width / 2) - 30;
    const circleY = 20;

    const circleWin = createCircleWindow(circleX, circleY);
    circleWin.show();
    circleWin.focus();
}

function restoreFromCircle() {
    if (!mainWindow) return;

    isMinimized = false;

    mainWindow.show();
    mainWindow.setAlwaysOnTop(true, 'screen-saver');

    if (circleWindow) {
        circleWindow.hide();
    }
}

/* ======================================================
   TRAY (UNCHANGED)
   ====================================================== */
function createTray() {
    const icon = nativeImage.createFromDataURL(LOGO_BASE64);
    tray = new Tray(icon);

    const contextMenu = Menu.buildFromTemplate([
        {
            label: 'Show Interview Helper',
            click: () => isMinimized ? restoreFromCircle() : mainWindow.show()
        },
        {
            label: 'Minimize to Circle',
            click: minimizeToCircle
        },
        { type: 'separator' },
        {
            label: 'Quit',
            click: () => app.quit()
        }
    ]);

    tray.setToolTip('Interview Helper');
    tray.setContextMenu(contextMenu);

    tray.on('click', () => {
        if (isMinimized) restoreFromCircle();
        else mainWindow.show();
    });
}

/* ======================================================
   BACKEND (UNCHANGED)
   ====================================================== */
function startBackend() {
    const pythonPath = process.platform === 'win32' ? 'python' : 'python3';
    const scriptPath = path.join(__dirname, 'main.py');

    pythonServer = spawn(pythonPath, [scriptPath]);

    pythonServer.stdout.on('data', d => console.log(`Backend: ${d}`));
    pythonServer.stderr.on('data', d => console.error(`Backend Error: ${d}`));
}

/* ======================================================
   APP LIFECYCLE (UNCHANGED)
   ====================================================== */
app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        if (pythonServer) pythonServer.kill();
        app.quit();
    }
});

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
    }
});

// 🔥 Clean up global shortcuts on quit
app.on('will-quit', () => {
    globalShortcut.unregisterAll();
    console.log('🧹 Global hotkeys unregistered');
});

app.on('before-quit', () => {
    if (pythonServer) pythonServer.kill();
    if (circleWindow) circleWindow.close();
});