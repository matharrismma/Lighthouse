# Lighthouse Edge v0.1 — Distribution Guide

## What you have

**lighthouse_edge_v01.html** — A single HTML file containing the complete app:
- Four Gates deterministic engine (RED → FLOOR → WAY → EXECUTION)
- Scriptural authority from the World English Bible anchored to every gate
- Calibre formation engine (alignment, chaff, fruit, tier progression)
- Packet form, history, detail views
- NFC tag simulation (prefills maintenance packets)
- External data fetch → packet generation
- Full state export/import (JSON)
- localStorage auto-save (survives browser restarts)
- Tier-influenced gate thresholds (MILK vs MEAT)

**lighthouse_edge.jsx** — The React artifact source (runs inside Claude.ai)

---

## How to share it

### 1. Direct file sharing (fastest)
Copy **lighthouse_edge_v01.html** to:
- Email attachment
- USB drive
- microSD card
- Shared folder
- Text message (as file)

The recipient opens it in any browser. That's it.

### 2. Old Android phone as dedicated terminal
1. Copy the HTML file to the phone (USB, SD card, Bluetooth, email)
2. Open in Chrome or any browser
3. Chrome menu → "Add to Home screen"
4. The app appears as an icon on the home screen
5. Runs like a native app, dark theme, full screen

### 3. Multiple devices with shared state
- Device A: Use the app, create packets, run evaluations
- Device A: Export → "Export Full State (microSD)" → saves a JSON file
- Copy that JSON file to Device B (SD card, USB, email)
- Device B: Open the app → Export → "Import State from File"
- Device B now has all packets and the Calibre state from Device A

This is the offline-first sync model. No cloud. No accounts. File transfer is the protocol.

### 4. Host on a local network (optional)
If you want multiple people on the same wifi to access it:
```
# On any machine with Python installed:
cd /folder/containing/the/html/file
python3 -m http.server 8080
```
Others navigate to `http://your-ip:8080/lighthouse_edge_v01.html`

---

## What it needs to run

- A web browser (Chrome, Firefox, Safari, Edge — any version from the last 5+ years)
- Internet connection on **first load only** (to fetch React and fonts from CDN)
- After first load: works offline if browser caches the resources
- localStorage for auto-save between sessions

### For true air-gapped / no-internet operation
The HTML file currently loads React, Babel, and fonts from CDN on first open.
For a fully self-contained version (no internet ever), the next step is a bundled build
that inlines all dependencies. This is a straightforward build step for your developer.

---

## How the formation model works

Every packet you evaluate feeds the Calibre engine:

1. **Gate result** → signals: PROCEED generates fruit, WAIT shows caution is working, REJECT shows the line held
2. **Signals** → Calibre state: alignment, chaff, fruit, streaks all update
3. **Calibre state** → gate thresholds: a MILK-tier user gets strict gates; a MEAT-tier user with high alignment gets WAY-level latitude

The path narrows with use because:
- Consistent, well-formed decisions (adequate basis, witness present, appropriate risk) **build alignment**
- Alignment streaks + access progress → eventual MILK → MEAT upgrade
- MEAT doesn't mean loose — RED lines never move, FLOOR still requires basis
- MEAT means the system trusts your operational judgment on WAY-level constraints

The framework gets more **precise**, not more permissive.

---

## State portability

The Export Full State button produces a JSON file like:
```json
{
  "version": "0.1.0",
  "exportedAt": "2026-03-14T...",
  "calibre": {
    "tier": "MILK",
    "align": 0.42,
    "chaff": 0.08,
    "fruit": 1.23,
    ...
  },
  "packets": [ ... ]
}
```

This is your complete portable state. Copy it to a new device, import it,
and you pick up exactly where you left off. The Calibre formation state
travels with the packets.

---

## Next steps

| Step | What | Who |
|------|------|-----|
| Now | Share the HTML file with test users | Matt |
| Soon | Bundle dependencies for true offline (no CDN) | Developer |
| Soon | Add real NFC via Web NFC API (Chrome on Android) | Developer |
| Later | Native Kotlin port using this as reference implementation | Developer |
| Later | Hardware witness nodes (ESP32 + LoRa) | Hardware team |

---

## File inventory

```
lighthouse_edge_v01.html          ← The app (share this)
lighthouse_edge.jsx               ← React source (for Claude.ai artifact)
Lighthouse_Edge_Developer_Pack_v0_1.zip  ← Original builder spec
```
