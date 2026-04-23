# 🔥 CLICK-THROUGH OVERLAY - COMPLETE SETUP GUIDE

## ⚡ QUICK START

### Step 1: Update your `index.html`
Add this AFTER your styles.css:
```html
<link rel="stylesheet" href="OVERLAY_FIX.css" />
```

### Step 2: Update your `renderer.js`
Add this AFTER the DOMContentLoaded event:
```javascript
// At the end of your initialize() function, add:
ClickThroughOverlay.init();
```

### Step 3: Include the overlay script
Add this BEFORE closing </body> in index.html:
```html
<script src="OVERLAY_FIX.js"></script>
```

---

## 🎯 HOW IT WORKS

### Click-Through Behavior
```
┌─────────────────────────────────────┐
│     OVERLAY (pointer-events: none)  │
│  ┌─────────────────────────────────┐│
│  │ [Button]  [Button]  [Button]   ││ ← Button: pointer-events: auto
│  │         (captures clicks)        ││
│  └─────────────────────────────────┘│
│                                     │
│  Empty Space → Clicks pass through │
│  ↓                                  │
│  ┌─────────────────────────────────┐│
│  │ BACKGROUND APP                  ││
│  │ (receives click)                 ││
│  └─────────────────────────────────┘│
└─────────────────────────────────────┘
```

### Keyboard Controls

| Key Combo | Action |
|-----------|--------|
| **Ctrl + ← Arrow** | Move overlay LEFT |
| **Ctrl + → Arrow** | Move overlay RIGHT |
| **Ctrl + ↑ Arrow** | Move overlay UP |
| **Ctrl + ↓ Arrow** | Move overlay DOWN |
| **Tab** | Navigate to next button |
| **Shift + Tab** | Navigate to previous button |
| **← / →** | Move between buttons |
| **Enter / Space** | Click focused button |

---

## ✅ TESTING CHECKLIST

- [ ] Click overlay buttons → They activate ✅
- [ ] Click empty overlay space → Click passes to app behind ✅
- [ ] Press Ctrl+Right → Overlay moves right ✅
- [ ] Press Ctrl+Left → Overlay moves left ✅
- [ ] Press Ctrl+Up → Overlay moves up ✅
- [ ] Press Ctrl+Down → Overlay moves down ✅
- [ ] Press Tab → Focus moves between buttons ✅
- [ ] Press Enter → Focused button clicks ✅
- [ ] Mouse works on background UI → Works ✅

---

## 🔧 IF NOT WORKING

### Issue: Clicks not reaching background app
**Solution:** Check that `.ai-overlay-bar { pointer-events: none; }` is in CSS

### Issue: Overlay buttons don't work
**Solution:** Check that buttons have `pointer-events: auto;`

### Issue: Keyboard navigation doesn't work
**Solution:** Make sure `step4-active` class is applied to body when overlay is shown

### Issue: Overlay doesn't move
**Solution:** Verify Ctrl+Arrow keys are being captured (check console)

---

## 📝 FILE LOCATIONS

```
electron/
├── OVERLAY_FIX.js        ← Include this
├── OVERLAY_FIX.css       ← Include this
├── index.html            ← Update (add script tags)
├── renderer.js           ← Update (call ClickThroughOverlay.init())
├── styles.css            ← Replace old overlay CSS with OVERLAY_FIX.css
└── main.js               ← Window size (already 1600x600 ✅)
```

---

## 🚀 INITIALIZATION ORDER

```javascript
// In your initialize() function:

1. setupCursorControl();
2. setupOverlayMovement();  // OLD - remove this
3. setupMousePrevention();  // OLD - remove this
4. setupOverlayKeyboardNavigation(); // OLD - remove this

// Replace with:
5. ClickThroughOverlay.init(); // NEW - handles everything!

// Rest of setup...
```

---

## 💡 KEY FEATURES

✅ **Click-through:** Clicks on empty overlay space pass to app behind  
✅ **Button capture:** Overlay buttons work normally  
✅ **Keyboard control:** Full keyboard navigation  
✅ **Movement:** Ctrl+Arrow keys move overlay smoothly  
✅ **Mouse + Keyboard:** Both work together  
✅ **Perplexity AI style:** Exactly like the real app  

---

## 🎮 USAGE EXAMPLE

```
User opens app:
1. Overlay appears (on top of Chrome/Word/etc.)
2. User clicks Chrome button → Chrome processes click ✅
3. User clicks overlay button → Overlay handles it ✅
4. User presses Ctrl+Right → Overlay moves right ✅
5. User presses Tab → Highlights next overlay button ✅
6. User presses Enter → Focused button clicks ✅
```

---

## 📞 TROUBLESHOOTING

**Still not working?**
- Open DevTools (F12)
- Check Console for errors
- Look for "✅" log messages confirming initialization
- Check Network tab to ensure OVERLAY_FIX.js loaded

---

**Created:** April 17, 2026  
**Version:** 1.0 - Complete Click-Through Overlay System
