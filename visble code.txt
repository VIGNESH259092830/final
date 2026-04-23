function startBackend() {
    const isProd = app.isPackaged;

    let command;
    let args = [];

    if (isProd) {
        // ✅ PRODUCTION: run packaged backend.exe
        command = path.join(process.resourcesPath, 'backend', 'backend.exe');
    } else {
        // ✅ DEVELOPMENT: run python main.py
        command = process.platform === 'win32' ? 'python' : 'python3';
        args = [path.join(__dirname, '..', 'app', 'main.py')];
    }

    pythonServer = spawn(command, args, {
        detached: true,
        stdio: isProd ? 'ignore' : 'pipe'
    });

    pythonServer.unref();

    if (!isProd) {
        pythonServer.stdout.on('data', d =>
            console.log(`Backend: ${d.toString()}`)
        );
        pythonServer.stderr.on('data', d =>
            console.error(`Backend Error: ${d.toString()}`)
        );
    }
}


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
   CREATE MAIN WINDOW
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
        skipTaskbar: false,
        alwaysOnTop: true,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js')
        }
    });

    mainWindow.setContentProtection(false);
    mainWindow.setAlwaysOnTop(true, 'screen-saver');
    mainWindow.loadFile('index.html');
    
    // REMOVE IN PRODUCTION: Enable for debugging
    // mainWindow.webContents.openDevTools();

    createTray();
    startBackend();

    /* ================= IPC HANDLERS ================= */
    ipcMain.on('minimize-window', minimizeToCircle);
    ipcMain.on('close-window', () => app.quit());
    ipcMain.on('restore-window', restoreFromCircle);

    ipcMain.on('move-circle', (event, x, y) => {
        if (circleWindow) {
            circleWindow.setPosition(x, y);
        }
    });

    /* ======================================================
       PREVENT AUTO HIDE / AUTO MINIMIZE
       ====================================================== */
    mainWindow.on('minimize', (e) => {
        e.preventDefault();
        mainWindow.show();
        mainWindow.focus();
    });

    mainWindow.on('blur', () => {
        if (!isMinimized && mainWindow) {
            mainWindow.show();
            mainWindow.setAlwaysOnTop(true, 'screen-saver');
        }
    });

    mainWindow.on('hide', () => {
        if (!isMinimized) {
            mainWindow.show();
        }
    });
}

/* ======================================================
   CIRCLE WINDOW
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

    circleWindow.setContentProtection(false);
    circleWindow.setAlwaysOnTop(true, 'screen-saver');
    circleWindow.loadFile('circle.html');
    
    // REMOVE IN PRODUCTION: Enable for debugging
    // circleWindow.webContents.openDevTools();

    circleWindow.on('closed', () => {
        circleWindow = null;
    });

    return circleWindow;
}

/* ======================================================
   MINIMIZE TO CIRCLE
   ====================================================== */
function minimizeToCircle() {
    if (!mainWindow) return;

    isMinimized = true;
    mainWindow.hide();
    mainWindow.setSkipTaskbar(true);

    // POSITION AT TOP CENTER OF SCREEN
    const { width, height } = screen.getPrimaryDisplay().workAreaSize;
    const circleX = Math.floor((width - 60) / 2); // Center horizontally
    const circleY = 20; // 20px from top

    const circleWin = createCircleWindow(circleX, circleY);
    circleWin.show();
    circleWin.focus();
}

/* ======================================================
   RESTORE FROM CIRCLE
   ====================================================== */
function restoreFromCircle() {
    if (!mainWindow) return;

    isMinimized = false;
    mainWindow.setSkipTaskbar(false);
    mainWindow.show();
    mainWindow.focus();
    mainWindow.setAlwaysOnTop(true, 'screen-saver');

    if (circleWindow) {
        circleWindow.hide();
    }
}

/* ======================================================
   TRAY
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
   BACKEND START - YOUR EXISTING CODE
   ====================================================== */
function startBackend() {
    const isProd = app.isPackaged;

    let command;
    let args = [];

    if (isProd) {
        command = path.join(process.resourcesPath, 'backend', 'backend.exe');
    } else {
        command = process.platform === 'win32' ? 'python' : 'python3';
        args = [path.join(__dirname, '..', 'app', 'main.py')];
    }

    pythonServer = spawn(command, args, {
        detached: true,
        stdio: isProd ? 'ignore' : 'pipe'
    });

    pythonServer.unref();

    if (!isProd) {
        pythonServer.stdout.on('data', d =>
            console.log(`Backend: ${d.toString()}`)
        );
        pythonServer.stderr.on('data', d =>
            console.error(`Backend Error: ${d.toString()}`)
        );
    }
}

/* ======================================================
   APP LIFECYCLE
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