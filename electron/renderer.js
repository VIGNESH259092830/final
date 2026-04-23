// renderer.js - COMPLETE FIXED VERSION - ONLY fetch handles AI streams
// 🔥 CRITICAL FIX: SSE only handles transcripts, NO AI events in SSE

document.addEventListener("DOMContentLoaded", function() {
    console.log("🚀 Interview Helper Frontend Initializing...");
    
    // ================= GLOBAL STATE =================
    let sseConnection = null;
    let currentTranscript = "";
    let micMuted = false;
    let systemMuted = false;
    let isAiResponding = false;
    let sessionTimer = null;
    let sessionStartTime = null;
    let currentSessionId = null;
    let isSessionActive = false;
    let reconnectAttempts = 0;
    const MAX_RECONNECT_ATTEMPTS = 10;
    
    // 🔥 NEW: Overlay position for arrow key movement (both X and Y)
    let overlayPositionX = 0;  // Horizontal position (left/right)
    let overlayPositionY = 0;  // Vertical position (up/down)
    const OVERLAY_MOVE_STEP = 20;
    
    // Duplicate prevention tracking
    let lastProcessedText = "";
    let lastProcessedTime = 0;
    let lastPartialText = "";
    let lastFinalText = "";
    let duplicateBlockList = new Set();
    
    // Scroll management
    let isAutoScrollEnabled = false;
    let lastUserScrollTime = Date.now();
    const AUTO_SCROLL_THRESHOLD = 2000;
    
    // ================= DRAG ANYWHERE =================
    let isDragging = false;
    let dragStartX = 0;
    let dragStartY = 0;
    
    // ================= ELEMENTS =================
    const qaQuestion = document.getElementById("qaQuestion");
    const qaAnswer = document.getElementById("qaAnswer");
    const btnAnswer = document.getElementById("btnAnswer");
    const btnClear = document.getElementById("btnClear");
    const btnMic = document.getElementById("btnMicIcon");
    const btnSystem = document.getElementById("btnSystemIcon");
    const btnBackToSettings = document.getElementById("btnBackToSettings");
    const btnToolbarCancel = document.getElementById("btnToolbarCancel");
    const btnCollapse = document.getElementById("toolbarCollapse");
    const durationLabel = document.getElementById("durationLabel");
    const toolbarDuration = document.getElementById("toolbarDuration");
    
    // Form elements
    const companyInput = document.getElementById("companyInput");
    const jobDescInput = document.getElementById("jobDescInput");
    const resumeText = document.getElementById("resumeText");
    const contextInput = document.getElementById("contextInput");
    
    // Tab elements
    const tabs = document.querySelectorAll(".tab");
    const tabPanels = document.querySelectorAll(".tab-panel");
    
    // Chat elements
    const chatInput = document.getElementById("chatInput");
    const btnSendChat = document.getElementById("chatSend");
    const toolbarChat = document.getElementById("toolbarChat");
    const chatRow = document.getElementById("chatRow");
    
    // Session elements
    const sessionList = document.getElementById("sessionList");
    const sessionMeta = document.getElementById("sessionMeta");
    const sessionMessages = document.getElementById("sessionMessages");
    
    // Window elements for dragging
    const windowShell = document.getElementById("windowShell");
    const aiToolbar = document.getElementById("aiToolbar");
        const aiPanel = document.getElementById("aiPanel");

        // ========== Overlay Q/A Panel Resize Logic ==========
        const resizeHandle = aiPanel ? aiPanel.querySelector(".ai-panel-resize") : null;
        let isResizing = false;
        let startY = 0;
        let startHeight = 0;
        let startX = 0;
        let startWidth = 0;

        if (resizeHandle && aiPanel) {
            resizeHandle.addEventListener("mousedown", function(e) {
                isResizing = true;
                startY = e.clientY;
                startHeight = aiPanel.offsetHeight;
                startX = e.clientX;
                startWidth = aiPanel.offsetWidth;
                document.body.style.userSelect = "none";
            });

            document.addEventListener("mousemove", function(e) {
                if (!isResizing) return;
                // Resize vertically and horizontally
                let newHeight = startHeight + (e.clientY - startY);
                let newWidth = startWidth + (e.clientX - startX);
                // Clamp to window size
                newHeight = Math.max(180, Math.min(window.innerHeight - aiPanel.offsetTop - 20, newHeight));
                newWidth = Math.max(320, Math.min(window.innerWidth - aiPanel.offsetLeft - 20, newWidth));
                aiPanel.style.height = newHeight + "px";
                aiPanel.style.width = newWidth + "px";
            });

            document.addEventListener("mouseup", function() {
                if (isResizing) {
                    isResizing = false;
                    document.body.style.userSelect = "";
                }
            });
        }

    // ================= 🔥 CURSOR CONTROL - NO HAND SYMBOLS =================
    function setupCursorControl() {
        console.log("🖱️ Setting up cursor control - NO HAND SYMBOLS");
        
        const cursorStyle = document.createElement('style');
        cursorStyle.id = 'cursor-control-style';
        cursorStyle.textContent = `
            /* ===== ARROW CURSOR FOR EVERYTHING - NO HAND SYMBOLS ===== */
            * {
                cursor: default !important;
            }
            
            button, .tab, .ctrl, .circle-icon, .square-icon, .pill, 
            .nav-btn, .primary-btn, .secondary-btn, a, .session-item,
            .clickable, [role="button"], [type="button"], [type="submit"],
            [type="reset"], .copy-button, .copy-code-btn, #toolbarChat,
            #chatSend, .window-control, .btn, .icon-button, .menu-item,
            .dropdown-item, .select-item, .option, .close-btn, .min-btn {
                cursor: default !important;
            }
            
            button:disabled, .ctrl:disabled, .pill:disabled,
            .nav-btn:disabled, .primary-btn:disabled {
                cursor: not-allowed !important;
            }
            
            input, textarea, .chat-input, [type="text"], [type="email"], 
            [type="password"], [contenteditable="true"], .editable {
                cursor: text !important;
            }
            
            /* ===== SCREEN SHARING - HIDE CURSOR COMPLETELY ===== */
            body.screen-sharing, body.screen-sharing * {
                cursor: none !important;
            }
            
            body.screen-sharing {
                caret-color: transparent;
            }
            
            .drag-region, .window-header, #windowShell, #aiToolbar, 
            .ai-panel-header, [data-drag-region="true"] {
                -webkit-app-region: drag;
            }
            
            .no-drag, button, input, textarea, select, a {
                -webkit-app-region: no-drag;
            }
            
            body.dragging, body.dragging * {
                cursor: grabbing !important;
            }
        `;
        
        const existingStyle = document.getElementById('cursor-control-style');
        if (existingStyle) existingStyle.remove();
        document.head.appendChild(cursorStyle);
        
        function detectScreenShare() {
            const isScreenSharing = 
                document.querySelector('video[src*="screen"]') !== null ||
                document.querySelector('video[src*="display"]') !== null ||
                document.querySelector('div[class*="screen-share"]') !== null ||
                document.querySelector('div[class*="presenting"]') !== null ||
                document.querySelector('div[class*="desktop-capture"]') !== null ||
                document.body.classList.contains('screen-share-active') ||
                document.querySelector('div[aria-label*="screen" i]') !== null ||
                document.querySelector('div[aria-label*="present" i]') !== null;
            
            if (isScreenSharing) {
                document.body.classList.add('screen-sharing');
                console.log("📺 Screen sharing detected - cursor hidden");
            } else {
                document.body.classList.remove('screen-sharing');
            }
        }
        
        setInterval(detectScreenShare, 1000);
        detectScreenShare();
        
        if (navigator.mediaDevices) {
            navigator.mediaDevices.addEventListener('devicechange', detectScreenShare);
        }
        
        console.log("✅ Cursor control active - NO HAND SYMBOLS, cursor hidden during screen share");
    }

    // ================= 🔥 OVERLAY MOVEMENT WITH CTRL+ARROW KEYS (UP/DOWN/LEFT/RIGHT) =================
 // ================= 🔥 GLOBAL HOTKEY HANDLER - UPDATED =================
window.electronAPI.onGlobalHotkey((data) => {
    const key = data.hotkey;
    const step = 20;
    
    console.log(`🌍 Global hotkey received: ${key}`);

    switch (key) {
        case 'answer':
            if (btnAnswer && !btnAnswer.disabled) {
                handleAnswerButton();
            }
            break;

        case 'clear':
            if (btnClear) {
                handleClearButton();
            }
            break;

        case 'chat':
            if (toolbarChat) {
                toolbarChat.click();
            }
            break;

        case 'mic':
            toggleMic();
            break;

        case 'system':
            toggleSystem();
            break;

        case 'move-left':
            moveOverlay(-step, 0);
            break;

        case 'move-right':
            moveOverlay(step, 0);
            break;

        case 'move-up':
            moveOverlay(0, -step);
            break;

        case 'move-down':
            moveOverlay(0, step);
            break;
            
        case 'scroll-down':
            scrollAnswerArea(100);
            break;
            
        case 'scroll-up':
            scrollAnswerArea(-100);
            break;
            
        case 'page-down':
            scrollAnswerArea(qaAnswer?.clientHeight * 0.8 || 400);
            break;
            
        case 'page-up':
            scrollAnswerArea(-(qaAnswer?.clientHeight * 0.8 || 400));
            break;
    }
});

// 🔥 Helper function for scrolling
function scrollAnswerArea(delta) {
    if (qaAnswer) {
        qaAnswer.scrollTop += delta;
        isAutoScrollEnabled = false;
        lastUserScrollTime = Date.now();
        console.log(`📜 Scrolled ${delta > 0 ? 'down' : 'up'} by ${Math.abs(delta)}px`);
    }
}
// ================= 🔥 OVERLAY MOVEMENT FUNCTION =================
function setupOverlayMovement() {
    console.log("📍 Setting up overlay movement...");
    // The actual movement is handled by the global hotkey handler
    // This function exists for initialization consistency
}

let posX = 0;
let posY = 0;

function moveOverlay(dx, dy) {
    posX += dx;
    posY += dy;

    const elements = [
        document.getElementById("aiToolbar"),
        document.getElementById("aiPanel")
    ];

    elements.forEach(el => {
        if (el) {
            el.style.transform = `translate(calc(-50% + ${posX}px), ${posY}px)`;
        }
    });
    
    console.log(`📍 Overlay moved to: (${posX}px, ${posY}px)`);
}
    // ================= STATUS UPDATES - NO ALERT TAB =================
    function updateAudioStatus() {
        if (btnMic) {
            btnMic.classList.toggle("is-on", !micMuted);
            btnMic.classList.toggle("is-off", micMuted);
            btnMic.title = micMuted ? "Microphone OFF - Click to unmute" : "Microphone ON - Click to mute";
        }
        
        if (btnSystem) {
            btnSystem.classList.toggle("is-on", !systemMuted);
            btnSystem.classList.toggle("is-off", systemMuted);
            btnSystem.title = systemMuted ? "System Audio OFF - Click to unmute" : "System Audio ON - Click to mute";
        }
        
        const micStatus = micMuted ? "OFF" : "ON";
        const sysStatus = systemMuted ? "OFF" : "ON";
        const micIcon = micMuted ? "🔇" : "🎤";
        const sysIcon = systemMuted ? "🔇" : "💻";
        
        if (toolbarDuration) {
            toolbarDuration.textContent = `${micIcon} ${micStatus} | ${sysIcon} ${sysStatus}`;
        }
        
        updateQAPanelIndicators(micMuted, systemMuted);
    }
    
    function updateQAPanelIndicators(isMicMuted, isSystemMuted) {
        const micIndicator = document.getElementById("micIndicator");
        const systemIndicator = document.getElementById("systemIndicator");
        const micIndicatorText = document.getElementById("micIndicatorText");
        const systemIndicatorText = document.getElementById("systemIndicatorText");
        
        if (micIndicator) {
            if (isMicMuted) {
                micIndicator.classList.add("muted");
                micIndicator.title = "Microphone: OFF";
                if (micIndicatorText) micIndicatorText.textContent = "OFF";
            } else {
                micIndicator.classList.remove("muted");
                micIndicator.title = "Microphone: ON";
                if (micIndicatorText) micIndicatorText.textContent = "ON";
            }
        }
        
        if (systemIndicator) {
            if (isSystemMuted) {
                systemIndicator.classList.add("muted");
                systemIndicator.title = "System Audio: OFF";
                if (systemIndicatorText) systemIndicatorText.textContent = "OFF";
            } else {
                systemIndicator.classList.remove("muted");
                systemIndicator.title = "System Audio: ON";
                if (systemIndicatorText) systemIndicatorText.textContent = "ON";
            }
        }
    }
    
    // ================= 🔥 CLICK-THROUGH OVERLAY (PARAKEET BEHAVIOR) =================
// ================= 🔥 CLICK-THROUGH OVERLAY (PARAKEET BEHAVIOR) =================
function setupMousePrevention() {
    console.log("🦜 Setting up Parakeet Behavior - Selective Interactivity...");
    
    const overlayBar = document.getElementById('aiToolbar');
    const overlayPanel = document.getElementById('aiPanel');
    
    // 🔥 KEY FIX: Don't block entire panel - let window-level control handle it
    if (overlayBar) {
        // Make the toolbar itself receive events (interactive elements inside handle)
        overlayBar.style.pointerEvents = 'auto';
        
        // Make buttons/icons interactive
        overlayBar.querySelectorAll('button, .circle-icon, .square-icon, .pill').forEach(el => {
            el.style.pointerEvents = 'auto';
        });
    }
    
    if (overlayPanel) {
        // 🔥 Don't set pointer-events: none on entire panel
        // Instead, let window-level setIgnoreMouseEvents() control it
        overlayPanel.style.pointerEvents = 'auto';
        
        // Make all interactive elements explicitly auto
        const interactiveElements = overlayPanel.querySelectorAll(`
            .ai-panel-header,
            .control-row,
            .qa-card,
            .chat-row,
            .qa-footer,
            button,
            input,
            textarea,
            select
        `);
        
        interactiveElements.forEach(el => {
            el.style.pointerEvents = 'auto';
        });
        
        // Make Q&A containers interactive
        const qaAnswer = overlayPanel.querySelector('#qaAnswer');
        const qaQuestion = overlayPanel.querySelector('#qaQuestion');
        if (qaAnswer) qaAnswer.style.pointerEvents = 'auto';
        if (qaQuestion) qaQuestion.style.pointerEvents = 'auto';
    }
    
    console.log("✅ Parakeet Behavior active:");
    console.log("   🟢 Interactive zones: buttons, Q&A card, inputs, header");
    console.log("   🔴 Non-interactive zones: controlled by click-through overlay");
}

    // ================= 🔥 CLICK-THROUGH OVERLAY SETUP =================
    function setupClickThroughOverlay() {
        console.log("🔥 Setting up click-through overlay behavior...");
        
        if (!window.electronAPI || !window.electronAPI.toggleClickThrough) {
            console.warn("⚠️ Electron API not available - click-through overlay disabled");
            return;
        }
        
        // 🔥 Track current interactive state to avoid redundant calls
        let currentInteractiveState = false;
        let lastCheckTime = 0;
        const THROTTLE_MS = 50;  // Check every 50ms max
        
        // 🔥 Track mouse movements to toggle click-through (with throttling)
        document.addEventListener('mousemove', (e) => {
            const now = Date.now();
            if (now - lastCheckTime < THROTTLE_MS) return;
            lastCheckTime = now;
            
            const element = document.elementFromPoint(e.clientX, e.clientY);
            const isInteractive = checkIfElementIsInteractive(element);
            
            // Only send if state changed (avoid spamming IPC)
            if (isInteractive !== currentInteractiveState) {
                currentInteractiveState = isInteractive;
                
                // Toggle click-through based on whether hovering over interactive element
                if (isInteractive) {
                    // Over interactive element: enable mouse events (DON'T ignore mouse)
                    window.electronAPI.toggleClickThrough(false);
                    console.log('✅ INTERACTIVE - Window receives clicks');
                } else {
                    // Over empty area: disable mouse events (ignore mouse, pass through)
                    window.electronAPI.toggleClickThrough(true);
                    console.log('🔴 PASS-THROUGH - Clicks go to apps behind');
                }
            }
        });
        
        // 🔥 Reset to pass-through when mouse leaves window
        document.addEventListener('mouseleave', () => {
            currentInteractiveState = false;
            window.electronAPI.toggleClickThrough(true);
            console.log('👋 Mouse left overlay - PASS-THROUGH enabled');
        });
        
        // 🔥 Initial state: pass-through
        window.electronAPI.toggleClickThrough(true);
        
        console.log("✅ Click-through overlay active");
        console.log("   🟢 Interactive elements: handle clicks");
        console.log("   🔴 Empty areas: clicks pass to apps behind");
    }
    
    // 🔥 Helper function to check if element should be interactive
    function checkIfElementIsInteractive(element) {
        if (!element) return false;
        
        // List of interactive elements
        const interactiveSelectors = [
            'button', 
            'input', 
            'textarea', 
            'select',
            'a',
            '.primary-btn',
            '.secondary-btn',
            '.tab',
            '.ctrl',
            '.circle-icon',
            '.square-icon',
            '.qa-card',
            '.chat-row',
            '.control-row',
            '.ai-panel-header',
            'label',
            '[role="button"]',
            '[contenteditable]'
        ];
        
        // Check if element or any parent is interactive
        let current = element;
        while (current && current !== document.body) {
            // Check tag name
            if (interactiveSelectors.includes(current.tagName.toLowerCase())) {
                return true;
            }
            
            // Check class names
            for (const selector of interactiveSelectors) {
                if (selector.startsWith('.') && current.classList.contains(selector.slice(1))) {
                    return true;
                }
            }
            
            // Check data attributes
            if (current.getAttribute('role') === 'button') {
                return true;
            }
            
            // Check pointer-events
            const pointerEvents = window.getComputedStyle(current).pointerEvents;
            if (pointerEvents === 'none') {
                return false;  // Stop checking up the chain if pointer-events is none
            }
            
            current = current.parentElement;
        }
        
        return false;
    }

    // ================= DRAG ANYWHERE FUNCTIONALITY =================
    function setupDragAnywhere() {
        console.log("🖱️ Setting up drag anywhere functionality...");
        
        if (document.querySelector('.circle-container')) {
            console.log("⭕ Circle window detected - skipping main window drag");
            return;
        }
        
        if (windowShell) {
            windowShell.removeEventListener('mousedown', startDrag);
            windowShell.addEventListener('mousedown', startDrag);
        }
        
        if (aiToolbar) {
            aiToolbar.removeEventListener('mousedown', startDrag);
            aiToolbar.addEventListener('mousedown', startDrag);
        }
        
        const aiPanelHeader = document.querySelector('.ai-panel-header');
        if (aiPanelHeader) {
            aiPanelHeader.removeEventListener('mousedown', startDrag);
            aiPanelHeader.addEventListener('mousedown', startDrag);
        }
        
        document.removeEventListener('mousemove', onDrag);
        document.removeEventListener('mouseup', stopDrag);
        document.addEventListener('mousemove', onDrag);
        document.addEventListener('mouseup', stopDrag);
        
        console.log("✅ Drag anywhere setup complete");
    }
    
    function startDrag(e) {
        if (e.target.tagName === 'BUTTON' || 
            e.target.tagName === 'INPUT' || 
            e.target.tagName === 'TEXTAREA' ||
            e.target.classList.contains('no-drag') ||
            e.target.closest('button')) {
            return;
        }
        
        isDragging = true;
        dragStartX = e.clientX;
        dragStartY = e.clientY;
        document.body.classList.add('dragging');
    }
    
    function onDrag(e) {
        if (!isDragging) return;
        e.preventDefault();
    }
    
    function stopDrag() {
        isDragging = false;
        document.body.classList.remove('dragging');
    }
    
    // ================= SESSION TIMER =================
    function startSessionTimer() {
        if (sessionTimer) clearInterval(sessionTimer);
        sessionStartTime = Date.now();
        
        sessionTimer = setInterval(() => {
            updateToolbarDuration();
            
            if (durationLabel) {
                durationLabel.textContent = "";
            }
        }, 1000);
    }
    
    function stopSessionTimer() {
        if (sessionTimer) {
            clearInterval(sessionTimer);
            sessionTimer = null;
        }
    }
    
    function updateToolbarDuration() {
        if (!sessionStartTime) return;
        
        const elapsed = Date.now() - sessionStartTime;
        const minutes = Math.floor(elapsed / 60000);
        const seconds = Math.floor((elapsed % 60000) / 1000);
        
        if (toolbarDuration) {
            const micStatus = micMuted ? "OFF" : "ON";
            const sysStatus = systemMuted ? "OFF" : "ON";
            const micIcon = micMuted ? "🔇" : "🎤";
            const sysIcon = systemMuted ? "🔇" : "💻";
            toolbarDuration.textContent = `${micIcon} ${micStatus} | ${sysIcon} ${sysStatus} | ⏱️ ${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        }
    }
    
    // ================= DUPLICATE DETECTION =================
    function isDuplicateText(existingText, newText) {
        if (!existingText || !newText) return false;
        
        const existingLower = existingText.toLowerCase().trim();
        const newLower = newText.toLowerCase().trim();
        
        if (existingLower === newLower) return true;
        
        if (duplicateBlockList.has(newLower)) {
            return true;
        }
        
        if (existingLower.includes(newLower)) {
            const existingWords = existingLower.split(/\s+/);
            const newWords = newLower.split(/\s+/);
            
            if (newWords.length <= 3) {
                const lastExistingWords = existingWords.slice(-newWords.length).join(' ');
                if (lastExistingWords === newWords.join(' ')) {
                    duplicateBlockList.add(newLower);
                    setTimeout(() => duplicateBlockList.delete(newLower), 1000);
                    return true;
                }
            }
        }
        
        const words = newLower.split(/\s+/);
        if (words.length === 2 && words[0] === words[1]) {
            duplicateBlockList.add(newLower);
            setTimeout(() => duplicateBlockList.delete(newLower), 1000);
            return true;
        }
        
        return false;
    }
    
   // ================= 🔥 FIXED SSE CONNECTION - HANDLES AI STATUS =================
function connectSSE() {
    if (sseConnection) {
        console.log("🔄 Closing existing SSE connection");
        sseConnection.close();
        sseConnection = null;
    }
    
    console.log("🔄 Connecting to SSE stream...");
    
    try {
        sseConnection = new EventSource("http://127.0.0.1:8000/stream");
        
        sseConnection.onopen = () => {
            console.log("✅ SSE connection established");
            reconnectAttempts = 0;
        };
        
        sseConnection.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                
                // 🔥 Handle AI status updates
                if (data.type === "ai_status") {
                    console.log(`🤖 AI status: ${data.is_responding ? 'responding' : 'idle'}`);
                    if (data.is_responding) {
                        qaQuestion.textContent = "AI is answering...";
                    }
                    return;
                }
                
                // Handle transcript events
                if (data.type === "transcript") {
                    // If AI is responding and this is a transcript, show in question area
                    if (data.ai_responding) {
                        if (data.text) {
                            qaQuestion.textContent = data.text;
                        }
                    } else {
                        handleTranscript(data);
                    }
                }
                
            } catch (error) {
                console.error("❌ SSE parse error:", error);
            }
        };
        
        sseConnection.onerror = (error) => {
            console.error("❌ SSE connection error:", error);
            
            if (sseConnection) {
                sseConnection.close();
                sseConnection = null;
            }
            
            reconnectAttempts++;
            if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                console.log(`🔄 Reconnecting (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})...`);
                setTimeout(connectSSE, 1000);
            } else {
                console.error("❌ Max reconnection attempts reached");
                if (qaQuestion) {
                    qaQuestion.textContent = "Connection lost. Please refresh.";
                }
            }
        };
        
    } catch (error) {
        console.error("❌ Failed to create SSE connection:", error);
        setTimeout(connectSSE, 1000);
    }
}
    
    // ================= TRANSCRIPT HANDLING =================
    function handleTranscript(data) {
        const text = data.text.trim();
        if (!text) {
            console.log("⚠️ Empty text in transcript");
            return;
        }
        
        const currentTime = Date.now();
        
        if (text === lastProcessedText && (currentTime - lastProcessedTime) < 300) {
            console.log(`🔄 Skipping immediate duplicate: "${text}"`);
            return;
        }
        
        lastProcessedText = text;
        lastProcessedTime = currentTime;
        
        console.log(`📥 ${data.source}: "${text}" (final: ${data.is_final})`);
        
        if (data.source === "mic" && micMuted) {
            console.log("🔇 Mic muted in UI - ignoring");
            return;
        }
        if (data.source === "system" && systemMuted) {
            console.log("🔇 System muted in UI - ignoring");
            return; 
        }
        
        if (data.is_final) {
            lastPartialText = "";
            
            const endsWithPunctuation = /[.!?]$/.test(currentTranscript.trim());
            const startsWithCapital = /^[A-Z]/.test(text.trim());
            
            if (endsWithPunctuation && startsWithCapital) {
                currentTranscript = text;
            } else if (!endsWithPunctuation && !startsWithCapital && currentTranscript) {
                if (!isDuplicateText(currentTranscript, text)) {
                    currentTranscript += " " + text;
                }
            } else {
                currentTranscript = text;
            }
            
            qaQuestion.textContent = currentTranscript;
            qaQuestion.classList.remove("partial-text");
            lastFinalText = text;
            
            console.log(`✅ Final transcript: "${currentTranscript}"`);
            
        } else if (data.is_partial) {
            if (text === lastPartialText) {
                return;
            }
            lastPartialText = text;
            
            qaQuestion.textContent = text;
            qaQuestion.classList.add("partial-text");
            
            console.log(`↗️ Partial preview: "${text}"`);
        }
    }
    
    // ================= CHAT BOX FUNCTIONALITY =================
    function setupChatBox() {
        if (!toolbarChat || !chatRow || !chatInput) {
            console.log("⚠️ Chat elements not found");
            return;
        }
        
        console.log("💬 Setting up chat box functionality...");
        
        toolbarChat.addEventListener("click", function(e) {
            e.stopPropagation();
            
            const isVisible = chatRow.style.display === "flex";
            chatRow.style.display = isVisible ? "none" : "flex";
            
            if (!isVisible) {
                setTimeout(() => {
                    chatInput.focus();
                    chatInput.select();
                }, 100);
            }
            
            toolbarChat.classList.toggle("active", !isVisible);
            console.log(`💬 Chat box ${isVisible ? 'hidden' : 'shown'}`);
        });
        
        chatInput.addEventListener("keypress", function(e) {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendChatQuestion();
            }
        });
        
        if (btnSendChat) {
            btnSendChat.addEventListener("click", function() {
                sendChatQuestion();
            });
        }
        
        document.addEventListener("click", function(e) {
            if (chatRow.style.display === "flex" && 
                !chatRow.contains(e.target) && 
                e.target !== toolbarChat &&
                !toolbarChat.contains(e.target)) {
                chatRow.style.display = "none";
                toolbarChat.classList.remove("active");
            }
        });
        
        console.log("✅ Chat box setup complete");
    }
    
    async function sendChatQuestion() {
        if (!chatInput || !chatInput.value.trim()) {
            showInAppAlert("Please enter a question");
            return;
        }
        
        const question = chatInput.value.trim();
        console.log(`💬 Sending chat question: "${question}"`);
        
        try {
            const originalAnswer = qaAnswer.innerHTML;
            qaAnswer.innerHTML = '<div class="thinking">Sending question...</div>';
            
            const response = await fetch("http://127.0.0.1:8000/api/chat-question", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: question })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.success) {
                chatInput.value = "";
                chatRow.style.display = "none";
                toolbarChat.classList.remove("active");
                
                currentTranscript = question;
                qaQuestion.textContent = question;
                qaQuestion.classList.remove("partial-text");
                
                console.log("✅ Chat question sent successfully");
                
                setTimeout(() => {
                    handleAnswerButton();
                }, 500);
            }
        } catch (error) {
            console.error("❌ Chat question failed:", error);
            qaAnswer.innerHTML = '<div class="error">Failed to send question. Please try again.</div>';
        }
    }
    
    // ================= TOGGLE BUTTONS - NO ALERTS =================
    async function toggleMic() {
        console.log("🎤 Toggling microphone...");
        
        try {
            const response = await fetch("http://127.0.0.1:8000/toggle-mic", {
                method: "POST"
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            
            micMuted = data.muted;
            updateAudioStatus();
            
            console.log(`✅ Mic ${micMuted ? 'muted' : 'unmuted'}`);
            
            if (!micMuted) {
                console.log("🔄 Mic unmuted - starting FRESH");
                currentTranscript = "";
                lastProcessedText = "";
                lastPartialText = "";
                lastFinalText = "";
                duplicateBlockList.clear();
                
                qaQuestion.textContent = "Listening...";
                qaQuestion.classList.remove("partial-text");
            }
            
        } catch (error) {
            console.error("❌ Toggle mic failed:", error);
            updateAudioStatus();
        }
    }
    
    async function toggleSystem() {
        console.log("💻 Toggling system audio...");
        
        try {
            const response = await fetch("http://127.0.0.1:8000/toggle-system", {
                method: "POST"
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            
            systemMuted = data.muted;
            updateAudioStatus();
            
            console.log(`✅ System ${systemMuted ? 'muted' : 'unmuted'}`);
            
            if (!systemMuted) {
                console.log("🔄 System unmuted - starting FRESH");
                currentTranscript = "";
                lastProcessedText = "";
                lastPartialText = "";
                lastFinalText = "";
                duplicateBlockList.clear();
                
                qaQuestion.textContent = "Listening...";
                qaQuestion.classList.remove("partial-text");
            }
            
        } catch (error) {
            console.error("❌ Toggle system failed:", error);
            updateAudioStatus();
        }
    }
    
 // ================= 🔥 ULTRA-FAST ANSWER BUTTON - FORCE IMMEDIATE RENDERING =================
async function handleAnswerButton() {
    if (!currentTranscript.trim()) {
        console.log("⚠️ No transcript to answer");
        showInAppAlert("Please speak or type a question first");
        return;
    }
    
    if (isAiResponding) {
        console.log("⚠️ AI is already responding");
        return;
    }
    
    const question = currentTranscript.trim();
    console.log(`🤖 Answering FRESH question: "${question}"`);
    
    isAiResponding = true;
    btnAnswer.disabled = true;
    
    const questionToSend = question;
    
    // Clear transcript immediately
    currentTranscript = "";
    lastProcessedText = "";
    lastPartialText = "";
    lastFinalText = "";
    duplicateBlockList.clear();
    
    qaQuestion.textContent = "AI is answering...";
    qaQuestion.classList.remove("partial-text");
    
    // 🔥 CRITICAL: Clear and prepare for streaming
    qaAnswer.innerHTML = '<div class="thinking">Preparing answer...</div>';
    qaAnswer.scrollTop = 0;
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);
    
    try {
        const response = await fetch("http://127.0.0.1:8000/api/answer-stream-fast", {
            method: "POST",
            headers: { 
                "Content-Type": "application/json",
                "Connection": "keep-alive",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache"
            },
            body: JSON.stringify({ text: questionToSend }),
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let rawAccumulatedText = ""; // Store raw text for formatting
        let aiResponseComplete = false;
        let firstTokenReceived = false;
        let firstRealTokenReceived = false;
        const startTime = Date.now();
        
        // 🔥 Create a container for streaming content
        let accumulatedHtml = '';
        
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            
            // 🔥 Split by double newline for SSE format
            const lines = buffer.split('\n\n');
            buffer = lines.pop() || "";
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const jsonStr = line.slice(6);
                        const data = JSON.parse(jsonStr);
                        
                        if (data.type === 'ai_stream') {
                            // Handle empty token (UI unfreezer)
                            if (data.content === ' ') {
                                if (!firstTokenReceived) {
                                    console.log(`⚡ UI UNFROZEN in ${Date.now() - startTime}ms`);
                                    firstTokenReceived = true;
                                }
                                continue;
                            }
                            
                            // 🔥 Handle first real token
                            if (!firstRealTokenReceived) {
                                firstRealTokenReceived = true;
                                const elapsed = Date.now() - startTime;
                                console.log(`⚡ FIRST REAL TOKEN: ${elapsed}ms ${elapsed <= 2000 ? '✅' : '❌'}`);
                                
                                // Start accumulating raw text
                                rawAccumulatedText = data.content;
                            } else {
                                // Append to raw text
                                rawAccumulatedText += data.content;
                            }
                            
                            // 🔥 FORMAT PROGRESSIVELY - Apply bullet point formatting to current text
                            accumulatedHtml = formatAIResponseProgressively(rawAccumulatedText);
                            qaAnswer.innerHTML = accumulatedHtml;
                            
                            // 🔥 FORCE MULTIPLE REPAINT STRATEGIES
                            
                            // Strategy 1: Force reflow
                            void qaAnswer.offsetHeight;
                            
                            // Strategy 2: Force style recalculation
                            window.getComputedStyle(qaAnswer).backgroundColor;
                            
                            // Strategy 3: Use requestAnimationFrame for next paint
                            requestAnimationFrame(() => {
                                // This forces a new frame
                            });
                            
                            // Strategy 4: Tiny timeout to break out of microtask queue
                            setTimeout(() => {}, 0);
                            
                            // Auto-scroll if enabled
                            if (isAutoScrollEnabled) {
                                qaAnswer.scrollTop = qaAnswer.scrollHeight;
                            }
                            
                            // Debug log every few tokens
                            if (rawAccumulatedText.length % 50 < 10) {
                                console.log(`📝 Token received at ${Date.now() - startTime}ms, length: ${rawAccumulatedText.length}`);
                            }
                        }
                        else if (data.type === 'ai_complete') {
                            const totalTime = Date.now() - startTime;
                            console.log(`✅ AI response complete in ${totalTime}ms`);
                            
                            isAiResponding = false;
                            btnAnswer.disabled = false;
                            
                            // Use the formatted version from the server for final display
                            if (data.content) {
                                qaAnswer.innerHTML = data.content;
                            } else {
                                // Fallback to our progressive formatting
                                qaAnswer.innerHTML = accumulatedHtml;
                            }
                            
                            aiResponseComplete = true;
                            
                            // Reset for next question
                            setTimeout(() => {
                                qaQuestion.textContent = "Listening for next question...";
                                qaQuestion.classList.remove("partial-text");
                            }, 500);
                        }
                        else if (data.type === 'ai_error') {
                            throw new Error(data.error);
                        }
                    } catch (parseError) {
                        console.warn("⚠️ Could not parse:", parseError, "Line:", line.substring(0, 50));
                    }
                }
            }
        }
        
        if (!aiResponseComplete) {
            isAiResponding = false;
            btnAnswer.disabled = false;
        }
        
    } catch (error) {
        clearTimeout(timeoutId);
        console.error("❌ AI streaming failed:", error);
        
        if (error.name === 'AbortError') {
            qaAnswer.innerHTML = '<div class="error">Request timed out. Please try again.</div>';
        } else {
            qaAnswer.innerHTML = `<div class="error">Error: ${error.message}</div>`;
        }
        
        isAiResponding = false;
        btnAnswer.disabled = false;
    }
}

function formatAIResponseProgressively(text) {
    if (!text || text.trim() === '') {
        return '<div class="thinking">Receiving answer...</div>';
    }
    
    // Split into lines for processing
    const lines = text.split('\n');
    let formattedHtml = '';
    let inBulletList = false;
    let inNumberedList = false;
    let inCodeBlock = false;
    let codeBlockLines = [];
    let codeLanguage = '';
    
    for (let i = 0; i < lines.length; i++) {
        let line = lines[i].trimRight();
        
        // Check for code block start/end
        if (line.trim().startsWith('```')) {
            if (!inCodeBlock) {
                // Start of code block
                inCodeBlock = true;
                codeLanguage = line.trim().substring(3).trim() || 'java';
                codeBlockLines = [];
                
                // Close any open lists
                if (inBulletList) {
                    formattedHtml += '</div>';
                    inBulletList = false;
                }
                if (inNumberedList) {
                    formattedHtml += '</div>';
                    inNumberedList = false;
                }
            } else {
                // End of code block
                inCodeBlock = false;
                const codeContent = codeBlockLines.join('\n');
                formattedHtml += `
                <div class="code-block">
                    <div class="code-header">
                        <span class="code-language">${escapeHtml(codeLanguage)}</span>
                        <button class="copy-code-btn">Copy</button>
                    </div>
                    <pre><code>${escapeHtml(codeContent)}</code></pre>
                </div>
                `;
            }
            continue;
        }
        
        // Inside code block - collect lines
        if (inCodeBlock) {
            codeBlockLines.push(line);
            continue;
        }
        
        // Skip empty lines but add spacing
        if (line.trim() === '') {
            if (inBulletList) {
                formattedHtml += '</div>';
                inBulletList = false;
            }
            if (inNumberedList) {
                formattedHtml += '</div>';
                inNumberedList = false;
            }
            formattedHtml += '<div class="paragraph-spacer" style="height: 12px;"></div>';
            continue;
        }
        
        // Check for numbered section headers (like "1. Short & Simple Original Theory")
        const numberedHeaderMatch = line.match(/^(\d+)\.\s+(.+)/);
        if (numberedHeaderMatch && line.length < 60) { // Headers are usually short
            if (inBulletList) {
                formattedHtml += '</div>';
                inBulletList = false;
            }
            if (inNumberedList) {
                formattedHtml += '</div>';
                inNumberedList = false;
            }
            
            const number = numberedHeaderMatch[1];
            const headerText = numberedHeaderMatch[2];
            
            formattedHtml += `
                <div class="section-header" style="
                    font-size: 16px;
                    font-weight: 600;
                    color: #3b82f6;
                    margin: 20px 0 12px 0;
                    padding-bottom: 4px;
                    border-bottom: 1px solid rgba(59, 130, 246, 0.3);
                ">
                    <span style="
                        display: inline-block;
                        background: #3b82f6;
                        color: white;
                        border-radius: 4px;
                        padding: 2px 8px;
                        margin-right: 8px;
                        font-size: 14px;
                    ">${number}</span>
                    ${escapeHtml(headerText)}
                </div>
            `;
            continue;
        }
        
        // Check for simple bullet points (-, •, *)
        const simpleBulletMatch = line.match(/^\s*[-•*]\s+(.+)/);
        if (simpleBulletMatch) {
            const content = simpleBulletMatch[1];
            
            if (!inBulletList) {
                formattedHtml += '<div class="bullet-list" style="margin: 8px 0 12px 0;">';
                inBulletList = true;
            }
            
            formattedHtml += `
                <div class="bullet-item" style="
                    display: flex;
                    margin: 8px 0;
                    line-height: 1.6;
                ">
                    <span style="
                        display: inline-block;
                        width: 20px;
                        color: #3b82f6;
                        font-size: 18px;
                        flex-shrink: 0;
                    ">•</span>
                    <span style="flex: 1;">${formatInlineCode(content)}</span>
                </div>
            `;
            continue;
        }
        
        // Check for numbered list items (1., 2., etc.)
        const numberedItemMatch = line.match(/^\s*(\d+)\.\s+(.+)/);
        if (numberedItemMatch) {
            const number = numberedItemMatch[1];
            const content = numberedItemMatch[2];
            
            if (!inNumberedList) {
                formattedHtml += '<div class="numbered-list" style="margin: 8px 0 12px 0;">';
                inNumberedList = true;
            }
            
            formattedHtml += `
                <div class="numbered-item" style="
                    display: flex;
                    margin: 8px 0;
                    line-height: 1.6;
                ">
                    <span style="
                        display: inline-block;
                        width: 28px;
                        color: #3b82f6;
                        font-weight: 500;
                        flex-shrink: 0;
                    ">${number}.</span>
                    <span style="flex: 1;">${formatInlineCode(content)}</span>
                </div>
            `;
            continue;
        }
        
        // Regular paragraph text
        if (inBulletList) {
            formattedHtml += '</div>';
            inBulletList = false;
        }
        if (inNumberedList) {
            formattedHtml += '</div>';
            inNumberedList = false;
        }
        
        // Format paragraph with proper spacing
        formattedHtml += `
            <div class="text-paragraph" style="
                margin: 12px 0;
                line-height: 1.7;
                color: #e2e8f0;
            ">${formatInlineCode(line)}</div>
        `;
    }
    
    // Close any open lists
    if (inBulletList) {
        formattedHtml += '</div>';
    }
    if (inNumberedList) {
        formattedHtml += '</div>';
    }
    
    return formattedHtml;
}

// ================= 🔥 FORMAT INLINE CODE (NO BOLD MARKERS) =================
function formatInlineCode(text) {
    if (!text) return '';
    
    // First, remove any markdown bold markers (**text**)
    let cleanText = text.replace(/\*\*(.*?)\*\*/g, '$1');
    
    // Then handle inline code (text between backticks)
    if (!cleanText.includes('`')) {
        return escapeHtml(cleanText);
    }
    
    let result = '';
    let parts = cleanText.split('`');
    
    for (let i = 0; i < parts.length; i++) {
        if (i % 2 === 0) {
            // Regular text - escape it
            result += escapeHtml(parts[i]);
        } else {
            // Code - wrap in code tag but don't bold
            result += `<code class="inline-code" style="
                background: rgba(59, 130, 246, 0.2);
                color: #93c5fd;
                padding: 2px 6px;
                border-radius: 4px;
                font-family: 'JetBrains Mono', monospace;
                font-size: 0.9em;
            ">${escapeHtml(parts[i])}</code>`;
        }
    }
    
    return result;
}

// ================= 🔥 ADD CSS FOR BETTER READABILITY =================
function addReadabilityStyles() {
    const style = document.createElement('style');
    style.textContent = `
        /* Main answer container */
        #qaAnswer {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            font-size: 15px;
            line-height: 1.7;
            color: #e2e8f0;
            padding: 20px;
            max-width: 800px;
            margin: 0 auto;
        }
        
        /* Section headers (1., 2., etc.) */
        .section-header {
            font-size: 18px;
            font-weight: 600;
            margin: 28px 0 16px 0;
            padding-bottom: 8px;
            border-bottom: 2px solid rgba(59, 130, 246, 0.3);
            color: #f0f9ff;
        }
        
        .section-header span:first-child {
            display: inline-block;
            background: #3b82f6;
            color: white;
            border-radius: 6px;
            padding: 4px 12px;
            margin-right: 12px;
            font-size: 16px;
            font-weight: 500;
        }
        
        /* Bullet points */
        .bullet-list {
            margin: 16px 0 20px 0;
        }
        
        .bullet-item {
            display: flex;
            margin: 12px 0;
            line-height: 1.7;
            align-items: flex-start;
        }
        
        .bullet-item span:first-child {
            display: inline-block;
            width: 24px;
            color: #3b82f6;
            font-size: 20px;
            flex-shrink: 0;
        }
        
        .bullet-item span:last-child {
            flex: 1;
        }
        
        /* Numbered lists */
        .numbered-list {
            margin: 16px 0 20px 0;
        }
        
        .numbered-item {
            display: flex;
            margin: 12px 0;
            line-height: 1.7;
            align-items: flex-start;
        }
        
        .numbered-item span:first-child {
            display: inline-block;
            width: 32px;
            color: #3b82f6;
            font-weight: 500;
            flex-shrink: 0;
        }
        
        .numbered-item span:last-child {
            flex: 1;
        }
        
        /* Regular paragraphs */
        .text-paragraph {
            margin: 16px 0;
            line-height: 1.7;
        }
        
        /* Paragraph spacing */
        .paragraph-spacer {
            height: 12px;
        }
        
        /* Inline code */
        .inline-code {
            background: rgba(59, 130, 246, 0.15);
            color: #93c5fd;
            padding: 3px 8px;
            border-radius: 6px;
            font-family: 'JetBrains Mono', 'Fira Code', monospace;
            font-size: 0.9em;
            border: 1px solid rgba(59, 130, 246, 0.2);
        }
        
        /* Code blocks */
        .code-block {
            margin: 24px 0;
            background: #1e293b;
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid #334155;
        }
        
        .code-header {
            background: #0f172a;
            padding: 10px 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #334155;
        }
        
        .code-language {
            color: #94a3b8;
            font-size: 13px;
            font-weight: 500;
            text-transform: uppercase;
        }
        
        .copy-code-btn {
            background: #334155;
            border: none;
            color: #e2e8f0;
            padding: 4px 12px;
            border-radius: 6px;
            font-size: 12px;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .copy-code-btn:hover {
            background: #3b82f6;
        }
        
        .code-block pre {
            margin: 0;
            padding: 20px;
            overflow-x: auto;
        }
        
        .code-block code {
            font-family: 'JetBrains Mono', 'Fira Code', monospace;
            font-size: 14px;
            line-height: 1.6;
            color: #e2e8f0;
        }
        
        /* Thinking animation */
        .thinking {
            color: #94a3b8;
            font-style: italic;
            padding: 20px;
            text-align: center;
            animation: pulse 1.5s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 0.7; }
            50% { opacity: 1; }
        }
    `;
    document.head.appendChild(style);
}

// Call this in your initialize function
addReadabilityStyles();
    // ================= 🔥 CLEAR BUTTON - SHIFT KEY REMOVED =================
    async function handleClearButton() {
        console.log("🔄 Clear button clicked - Fresh start (Shift key no longer does this)");
        
        currentTranscript = "";
        lastProcessedText = "";
        lastPartialText = "";
        lastFinalText = "";
        duplicateBlockList.clear();
        
        qaQuestion.textContent = "Listening for new question...";
        qaQuestion.classList.remove("partial-text");
        
        if (chatRow && chatRow.style.display === "flex") {
            chatRow.style.display = "none";
            toolbarChat.classList.remove("active");
        }
        
        try {
            await fetch("http://127.0.0.1:8000/api/clear-and-reset", {
                method: "POST"
            });
            console.log("✅ Fresh start initiated");
        } catch (error) {
            console.warn("⚠️ Could not notify backend:", error);
        }
    }
    
    // ================= IN-APP ALERT FUNCTION =================
    function showInAppAlert(message) {
        qaAnswer.innerHTML = `
            <div class="alert-message" style="animation: slideIn 0.3s ease;">
                <strong>⚠️ ${message}</strong>
            </div>
        `;
        
        setTimeout(() => {
            if (qaAnswer.innerHTML.includes("alert-message")) {
                if (qaAnswer.innerHTML.includes(message)) {
                    qaAnswer.innerHTML = "";
                }
            }
        }, 3000);
    }
    
    // ================= DATABASE: SESSION MANAGEMENT =================
    async function createSession() {
        const company = companyInput.value.trim();
        const jobDesc = jobDescInput.value.trim();
        const resume = resumeText.value.trim();
        const context = contextInput.value.trim();
        
        if (!company || !jobDesc || !resume) {
            showInAppAlert("Please fill in all required fields: Company, Job Description, and Resume");
            return;
        }
        
        console.log("💾 Creating session...");
        
        try {
            const response = await fetch("http://127.0.0.1:8000/api/session/create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    company: company,
                    job_description: jobDesc,
                    resume_text: resume,
                    extra_context: context
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.success) {
                currentSessionId = data.session_id;
                isSessionActive = true;
                
                document.body.classList.add("step4-active");
                document.getElementById("aiPanel").dataset.open = "true";
                
                micMuted = false;
                updateAudioStatus();
                
                currentTranscript = "";
                lastProcessedText = "";
                lastPartialText = "";
                lastFinalText = "";
                duplicateBlockList.clear();
                
                connectSSE();
                startSessionTimer();
                
                qaQuestion.textContent = "Session started! Ask your question...";
                qaAnswer.innerHTML = "";
                
                console.log(`✅ Session started with ID: ${currentSessionId}`);
                
                setTimeout(() => {
                    fetch("http://127.0.0.1:8000/api/clear-and-reset", {
                        method: "POST"
                    }).then(() => {
                        console.log("✅ Backend fresh listening started");
                    });
                }, 500);
                
            } else {
                throw new Error(data.error || "Failed to create session");
            }
            
        } catch (error) {
            console.error("❌ Session creation failed:", error);
            showInAppAlert(`Failed to create session: ${error.message}`);
        }
    }
    
    function stopSession() {
        console.log("🛑 Stopping session...");
        
        isSessionActive = false;
        
        document.body.classList.remove("step4-active");
        document.getElementById("aiPanel").dataset.open = "false";
        
        if (sseConnection) {
            sseConnection.close();
            sseConnection = null;
        }
        
        stopSessionTimer();
        
        currentTranscript = "";
        lastProcessedText = "";
        lastPartialText = "";
        lastFinalText = "";
        duplicateBlockList.clear();
        currentSessionId = null;
        
        if (chatRow && chatRow.style.display === "flex") {
            chatRow.style.display = "none";
            toolbarChat.classList.remove("active");
        }
        
        if (qaQuestion) {
            qaQuestion.textContent = "Session ended";
        }
        if (qaAnswer) {
            qaAnswer.innerHTML = "";
        }
        
        console.log("✅ Session stopped");
    }
    
    // ================= DATABASE: LOAD SESSIONS =================
    async function loadSessions() {
        try {
            const response = await fetch("http://127.0.0.1:8000/api/session/list");
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            
            if (!sessionList) return;
            
            if (data.success && data.sessions && data.sessions.length > 0) {
                sessionList.innerHTML = "";
                
                data.sessions.forEach(session => {
                    const sessionDate = new Date(session.created_at).toLocaleDateString('en-US', {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                    });
                    
                    const sessionItem = document.createElement("div");
                    sessionItem.className = "session-item";
                    sessionItem.innerHTML = `
                        <div class="session-header">
                            <strong>${session.company || 'Unnamed Company'}</strong>
                            <span class="session-date">${sessionDate}</span>
                        </div>
                        <div class="session-info">
                            <div class="job-preview">${session.job_description ? session.job_description.substring(0, 80) + '...' : 'No job description'}</div>
                        </div>
                        <div class="session-actions">
                            <button onclick="loadSessionDetails(${session.id})" class="nav-btn small">View</button>
                            <button onclick="deleteSession(${session.id})" class="nav-btn small delete-btn">Delete</button>
                        </div>
                    `;
                    sessionList.appendChild(sessionItem);
                });
                
                console.log(`✅ Loaded ${data.sessions.length} sessions`);
            } else {
                sessionList.innerHTML = '<div class="empty-state">No sessions found.</div>';
            }
        } catch (error) {
            console.error("❌ Error loading sessions:", error);
            if (sessionList) {
                sessionList.innerHTML = `<div class="error-state">Error: ${error.message}</div>`;
            }
        }
    }
    
    // ================= DATABASE: LOAD SESSION DETAILS =================
    window.loadSessionDetails = async function(sessionId) {
        try {
            const response = await fetch(`http://127.0.0.1:8000/api/session/${sessionId}`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.success && sessionMeta && sessionMessages) {
                const createdDate = new Date(data.session.created_at).toLocaleString();
                
                sessionMeta.innerHTML = `
                    <div class="session-detail-header">
                        <h3>${data.session.company || 'Unnamed Company'}</h3>
                        <div class="session-meta-info">
                            <span class="meta-item">Created: ${createdDate}</span>
                        </div>
                    </div>
                    <div class="session-detail-content">
                        <div class="detail-section">
                            <h4>Job Description</h4>
                            <div class="detail-content">${escapeHtml(data.session.job_description || 'No job description')}</div>
                        </div>
                        <div class="detail-section">
                            <h4>Resume Preview</h4>
                            <div class="detail-content">${escapeHtml(data.session.resume_text ? data.session.resume_text.substring(0, 300) + '...' : 'No resume')}</div>
                        </div>
                        <div class="detail-section">
                            <h4>Additional Context</h4>
                            <div class="detail-content">${escapeHtml(data.session.extra_context || 'No context')}</div>
                        </div>
                    </div>
                `;
                
                if (data.history && data.history.length > 0) {
                    sessionMessages.innerHTML = '<h4>Conversation History</h4>';
                    
                    data.history.forEach(msg => {
                        const msgDiv = document.createElement("div");
                        msgDiv.className = `msg-row ${msg.role}`;
                        
                        const roleIcon = msg.role === 'question' ? '❓' : '🤖';
                        const roleClass = msg.role === 'question' ? 'user' : 'assistant';
                        const roleText = msg.role === 'question' ? 'Question' : 'Answer';
                        
                        let timeText = '';
                        if (msg.created_at) {
                            try {
                                const date = new Date(msg.created_at);
                                timeText = date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                            } catch (e) {
                                timeText = msg.created_at;
                            }
                        }
                        
                        msgDiv.innerHTML = `
                            <div class="msg-header">
                                <span class="msg-role ${roleClass}">${roleIcon} ${roleText}</span>
                                <span class="msg-time">${timeText}</span>
                            </div>
                            <div class="msg-content">${escapeHtml(msg.content.substring(0, 500) + (msg.content.length > 500 ? '...' : ''))}</div>
                        `;
                        sessionMessages.appendChild(msgDiv);
                    });
                } else {
                    sessionMessages.innerHTML = '<div class="empty-state">No conversation history.</div>';
                }
                
                loadSessionIntoCurrent(data.session);
                
            }
        } catch (error) {
            console.error("❌ Error loading session details:", error);
            if (sessionMessages) {
                sessionMessages.innerHTML = `<div class="error-state">Error: ${error.message}</div>`;
            }
        }
    };
    
    function loadSessionIntoCurrent(session) {
        console.log(`📂 Loading session ${session.id} into current session`);
        
        if (companyInput) companyInput.value = session.company || '';
        if (jobDescInput) jobDescInput.value = session.job_description || '';
        if (resumeText) resumeText.value = session.resume_text || '';
        if (contextInput) contextInput.value = session.extra_context || '';
        
        currentSessionId = session.id;
        isSessionActive = true;
        
        document.body.classList.add("step4-active");
        document.getElementById("aiPanel").dataset.open = "true";
        
        currentTranscript = "";
        lastProcessedText = "";
        lastPartialText = "";
        lastFinalText = "";
        duplicateBlockList.clear();
        
        connectSSE();
        startSessionTimer();
        
        qaQuestion.textContent = `Loaded session: ${session.company || 'Unnamed Company'}`;
        qaAnswer.innerHTML = "<div class='info'>Session loaded. Ask new questions or continue the conversation.</div>";
        
        const sessionTab = document.querySelector('[data-tab="session"]');
        if (sessionTab) sessionTab.click();
        
        console.log(`✅ Session ${session.id} loaded successfully`);
    }
    
    // ================= DATABASE: DELETE SESSION =================
    window.deleteSession = async function(sessionId) {
        console.log(`🗑️ Deleting session ${sessionId}...`);
        
        try {
            const response = await fetch(`http://127.0.0.1:8000/api/session/${sessionId}`, {
                method: "DELETE"
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.success) {
                loadSessions();
                showInAppAlert("Session deleted successfully");
            }
        } catch (error) {
            console.error("❌ Error deleting session:", error);
            showInAppAlert(`Failed to delete session: ${error.message}`);
        }
    };
    
    // ================= SCROLL MANAGEMENT =================
    function setupArrowKeyNavigation() {
        console.log("⌨️ Setting up arrow key navigation...");
        
        document.addEventListener('keydown', function(event) {
            const activeElement = document.activeElement;
            const isInputFocused = activeElement.tagName === 'INPUT' || 
                                 activeElement.tagName === 'TEXTAREA' ||
                                 activeElement.isContentEditable;
            
            if (isInputFocused) {
                return;
            }
            
            const qaAnswer = document.getElementById("qaAnswer");
            if (!qaAnswer || qaAnswer.innerHTML.trim() === '') return;
            
            if (event.key === 'ArrowDown') {
                event.preventDefault();
                qaAnswer.scrollTop += 100;
                isAutoScrollEnabled = false;
                lastUserScrollTime = Date.now();
            } else if (event.key === 'ArrowUp') {
                event.preventDefault();
                qaAnswer.scrollTop -= 100;
                isAutoScrollEnabled = false;
                lastUserScrollTime = Date.now();
            } else if (event.key === 'PageDown') {
                event.preventDefault();
                qaAnswer.scrollTop += qaAnswer.clientHeight * 0.8;
                isAutoScrollEnabled = false;
                lastUserScrollTime = Date.now();
            } else if (event.key === 'PageUp') {
                event.preventDefault();
                qaAnswer.scrollTop -= qaAnswer.clientHeight * 0.8;
                isAutoScrollEnabled = false;
                lastUserScrollTime = Date.now();
            }
        });
    }
    

    // ================= CODE COPY FUNCTIONALITY =================
    function setupCodeCopyButtons() {
        document.addEventListener('click', function(event) {
            const copyButton = event.target.closest('.copy-button');
            if (copyButton && !copyButton.classList.contains('copied')) {
                const codeBlock = copyButton.closest('.chatgpt-code-block');
                const codeElement = codeBlock?.querySelector('code');
                
                if (codeElement) {
                    const codeText = codeElement.textContent;
                    
                    navigator.clipboard.writeText(codeText).then(() => {
                        copyButton.textContent = 'Copied!';
                        copyButton.classList.add('copied');
                        
                        setTimeout(() => {
                            copyButton.textContent = 'Copy';
                            copyButton.classList.remove('copied');
                        }, 2000);
                        
                        console.log("✅ Code copied to clipboard");
                    }).catch(err => {
                        console.error('❌ Failed to copy code:', err);
                        copyButton.textContent = 'Failed';
                        setTimeout(() => {
                            copyButton.textContent = 'Copy';
                        }, 2000);
                    });
                }
            }
        });
    }
    
    // ================= TAB MANAGEMENT =================
    function setupTabs() {
        tabs.forEach(tab => {
            tab.addEventListener("click", () => {
                tabs.forEach(t => t.classList.remove("active"));
                tabPanels.forEach(p => p.classList.remove("active"));
                
                tab.classList.add("active");
                
                const panelId = tab.getAttribute("data-tab");
                const panel = document.querySelector(`[data-panel="${panelId}"]`);
                if (panel) {
                    panel.classList.add("active");
                }
                
                if (panelId === "history") {
                    loadSessions();
                }
            });
        });
    }
    
    // ================= STEP NAVIGATION =================
    function setupSteps() {
        const steps = document.querySelectorAll(".step");
        
        function showStep(stepNumber) {
            steps.forEach(step => step.classList.remove("active"));
            const targetStep = document.querySelector(`.step-${stepNumber}`);
            if (targetStep) {
                targetStep.classList.add("active");
            }
            
            if (stepNumber === 4 && isSessionActive) {
                // Session is already active
            }
        }
        
        document.getElementById("btnFreeSession")?.addEventListener("click", () => showStep(2));
        document.getElementById("btnBack2")?.addEventListener("click", () => showStep(1));
        document.getElementById("btnNext2")?.addEventListener("click", () => showStep(3));
        document.getElementById("btnBack3")?.addEventListener("click", () => showStep(2));
        document.getElementById("btnCreate")?.addEventListener("click", createSession);
        
        document.getElementById("btnSaveSession")?.addEventListener("click", async () => {
            await createSession();
            showInAppAlert("Session saved!");
        });
    }
    
    // ================= EVENT LISTENERS =================
    function setupEventListeners() {
        if (btnMic) {
            btnMic.addEventListener("click", toggleMic);
        }
        if (btnSystem) {
            btnSystem.addEventListener("click", toggleSystem);
        }
        
        if (btnAnswer) {
            btnAnswer.addEventListener("click", handleAnswerButton);
        }
        if (btnClear) {
            btnClear.addEventListener("click", handleClearButton);
        }
        
        const btnBackSession = document.getElementById("btnBackSession");
        if (btnBackSession) {
            btnBackSession.addEventListener("click", function() {
                if (isSessionActive) {
                    stopSession();
                }
            });
        }
        
        if (btnBackToSettings) {
            btnBackToSettings.addEventListener("click", stopSession);
        }
        if (btnToolbarCancel) {
            btnToolbarCancel.addEventListener("click", stopSession);
        }
        
        if (btnCollapse) {
            btnCollapse.addEventListener("click", () => {
                const aiPanel = document.getElementById("aiPanel");
                if (aiPanel) {
                    aiPanel.classList.toggle("collapsed");
                    btnCollapse.textContent = aiPanel.classList.contains("collapsed") ? "˄" : "˅";
                }
            });
        }
    }
    
    // ================= WINDOW CONTROLS =================
    function setupWindowControls() {
        const btnMin = document.getElementById('btnMin');
        if (btnMin) {
            btnMin.addEventListener('click', (e) => {
                e.preventDefault();
                console.log('🔘 Minimize button clicked');
                if (window.electronAPI && window.electronAPI.minimizeWindow) {
                    window.electronAPI.minimizeWindow();
                }
            });
        }
        
        const btnClose = document.getElementById('btnClose');
        if (btnClose) {
            btnClose.addEventListener('click', (e) => {
                e.preventDefault();
                console.log('🔘 Close button clicked');
                if (window.electronAPI && window.electronAPI.closeWindow) {
                    window.electronAPI.closeWindow();
                }
            });
        }
    }
    
    // ================= CSS STYLES =================
    function addStyles() {
        const style = document.createElement('style');
        style.textContent = `
            /* 🔥 FIX 1: HAND CURSOR for all buttons */
            button, .tab, .ctrl, .circle-icon, .square-icon, .pill, 
            .session-item, .nav-btn, .copy-button, .copy-code-btn,
            #toolbarChat, #chatSend, [role="button"], [type="button"],
            [type="submit"], [type="reset"] {
                cursor: pointer !important;
            }
            
            button:disabled, .ctrl:disabled, .circle-icon:disabled,
            .square-icon:disabled, .pill:disabled, .nav-btn:disabled {
                cursor: not-allowed !important;
            }
            
            input[type="text"], input[type="email"], input[type="password"],
            textarea, select, .chat-input, .text-input {
                cursor: text !important;
            }
            
            /* 🔥 FIX 2: Screen sharing cursor visibility */
            * {
                caret-color: #3b82f6;
            }
            
            button:focus, .ctrl:focus, .circle-icon:focus, .square-icon:focus {
                outline: 2px solid #3b82f6 !important;
                outline-offset: 2px;
            }
            
            /* 🔥 DRAG ANYWHERE cursor */
            .drag-region, .window-shell, .ai-overlay-bar, .ai-panel-header {
                -webkit-app-region: drag;
            }
            
            .no-drag, button, input, textarea, select, a {
                -webkit-app-region: no-drag;
            }
            
            body.dragging, body.dragging * {
                cursor: grabbing !important;
                user-select: none;
            }
            
            /* Alert message styling - IN-APP, no tab */
            .alert-message {
                padding: 12px 16px;
                background-color: rgba(59, 130, 246, 0.2);
                border: 1px solid #3b82f6;
                border-radius: 8px;
                color: #f9fafb;
                margin: 10px 0;
                animation: slideIn 0.3s ease;
            }
            
            @keyframes slideIn {
                from { opacity: 0; transform: translateY(-10px); }
                to { opacity: 1; transform: translateY(0); }
            }
            
            .partial-text {
                color: #94a3b8 !important;
                font-style: italic !important;
            }
            
            .thinking {
                color: #94a3b8;
                font-style: italic;
                padding: 16px;
                display: flex;
                align-items: center;
                gap: 12px;
                animation: pulse 1.5s infinite;
            }
            
            .thinking:before {
                content: "";
                width: 16px;
                height: 16px;
                border: 2px solid #3b82f6;
                border-top-color: transparent;
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }
            
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
            
            @keyframes pulse {
                0%, 100% { opacity: 0.6; }
                50% { opacity: 1; }
            }
            
            .error {
                color: #f87171;
                padding: 12px;
                background: rgba(239, 68, 68, 0.1);
                border-radius: 6px;
                border-left: 4px solid #f87171;
            }
            
            /* Mic/System indicator states */
            .circle-icon.is-on {
                background: rgba(59, 130, 246, 0.3);
                border-color: #3b82f6;
                color: #3b82f6;
            }
            
            .circle-icon.is-off {
                opacity: 0.5;
                background: rgba(148, 163, 184, 0.1);
                border-color: rgba(148, 163, 184, 0.4);
                color: rgba(148, 163, 184, 0.6);
            }
        `;
        document.head.appendChild(style);
        console.log("✅ Styles added");
    }
    
    // ================= INITIALIZATION =================
    function initialize() {
        console.log("🔧 Initializing application with new features...");
        
        // 🔥 NEW: Cursor control - NO HAND SYMBOLS
        setupCursorControl();
        
        // 🔥 NEW: Overlay movement with arrow keys
        setupOverlayMovement();
        
        // 🔥 NEW: Prevent mouse pass-through to background
        setupMousePrevention();
        
        // 🔥 NEW: Click-through overlay (empty areas pass clicks)
        setupClickThroughOverlay();
        
        addStyles();
        setupWindowControls();
        setupTabs();
        setupSteps();
        setupEventListeners();
        setupChatBox();
       
        setupCodeCopyButtons();
        setupArrowKeyNavigation();
        setupDragAnywhere();
        
        micMuted = false;
        systemMuted = false;
        updateAudioStatus();
        isAutoScrollEnabled = false;
        
        document.querySelectorAll(".step").forEach(step => step.classList.remove("active"));
        document.querySelector(".step-1")?.classList.add("active");
        
        const modelSelect = document.getElementById("modelSelect");
        if (modelSelect) {
            modelSelect.innerHTML = `
                <option value="gpt-4o-mini" selected>GPT-4o Mini</option>
                <option value="gpt-4o">GPT-4o</option>
                <option value="gpt-4-turbo">GPT-4 Turbo</option>
            `;
        }
        
        const activeTab = document.querySelector('.tab.active');
        if (activeTab && activeTab.getAttribute('data-tab') === 'history') {
            loadSessions();
        }
        
        console.log("✅ Application initialized - NO HAND SYMBOLS, <> moves overlay, cursor hidden during screen share");
    }
    
    // ================= START APPLICATION =================
    initialize();
    
    setInterval(() => {
        if (isSessionActive && (!sseConnection || sseConnection.readyState === EventSource.CLOSED)) {
            console.log("🔄 SSE disconnected, reconnecting...");
            connectSSE();
        }
    }, 5000);
    
    window.loadSessionDetails = loadSessionDetails;
    window.deleteSession = deleteSession;
});

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}// Add this to your addStyles function in renderer.js
function addStyles() {
    const style = document.createElement('style');
    style.textContent = `
        /* Force hardware acceleration for smooth updates */
        #qaAnswer {
            will-change: contents;
            transform: translateZ(0);
            backface-visibility: hidden;
            perspective: 1000px;
        }
        
        /* Ensure thinking message is visible */
        .thinking {
            color: #94a3b8;
            font-style: italic;
            padding: 16px;
            animation: pulse 1.5s infinite;
        }
        
        /* Debug overlay to see updates */
        .debug-timer {
            position: fixed;
            bottom: 10px;
            right: 10px;
            background: rgba(0,0,0,0.8);
            color: #0f0;
            padding: 4px 8px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 12px;
            z-index: 9999;
            pointer-events: none;
        }
    `;
    document.head.appendChild(style);
    
    // Add debug timer
    const debugTimer = document.createElement('div');
    debugTimer.className = 'debug-timer';
    debugTimer.id = 'debugTimer';
    document.body.appendChild(debugTimer);
    
    // Update debug timer
    setInterval(() => {
        const timer = document.getElementById('debugTimer');
        if (timer) {
            timer.textContent = `UI Time: ${new Date().toLocaleTimeString()}.${Date.now() % 1000}`;
        }
    }, 100);
}