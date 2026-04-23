const { LOGO_BASE64 } = require('./logo.js');
const { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage, screen } = require('electron');
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
        width: 800,
        height: 600,
        minWidth: 780,
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
    startBackend();

    /* ================= IPC ================= */

    ipcMain.on('minimize-window', minimizeToCircle);
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
    });

    // ❌ Never allow OS hide
    mainWindow.on('hide', () => {
        if (!isMinimized) {
            mainWindow.show();
        }
    });
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
        movable: false,  // We handle movement manually
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

    // 🔐 Invisible to screen capture
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

    // Position at top center
    const { width } = screen.getPrimaryDisplay().workAreaSize;
    const circleX = Math.floor(width / 2) - 30; // 30 is half of 60px circle
    const circleY = 20; // 20px from top

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

app.on('before-quit', () => {
    if (pythonServer) pythonServer.kill();
    if (circleWindow) circleWindow.close();
});