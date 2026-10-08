# Secret Shop Bot

A bot to automate purchases in the Epic Seven Secret Shop, running via an Android emulator (BlueStacks or MEmu).

---

## System Requirements

- Windows 10 or later
- Python 3.13 or later
- Tesseract OCR installed
- Android emulator with the game open on the Secret Shop screen

---

## Python Dependencies

| Package | Purpose |
|---|---|
| uiautomator2 | Android device control via ADB |
| pytesseract | On-screen text detection via OCR |
| pillow | Screenshot capture and processing |

All other dependencies (adbutils, requests, etc.) are installed automatically.

---

## Installation

### 1. Tesseract OCR

Download and install Tesseract for Windows:
https://github.com/UB-Mannheim/tesseract/wiki

During installation, select the **Portuguese** (por) language pack.

The default installation path expected by the program is:

```
C:\Program Files\Tesseract-OCR\tesseract.exe
```

If you install it elsewhere, update this line in `main.py`:

```python
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

### 2. Python and dependencies

Create a virtual environment and install the pinned packages:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. ADB and emulator

The emulator must be running and reachable via ADB at `127.0.0.1:7555`.

To verify the connection, run:

```bash
adb connect 127.0.0.1:7555
adb devices
```

The device should appear as `connected`.

---

## Running

With the virtual environment active and the game open on the Secret Shop screen:

```bash
python main.py
```

---

## Using the Interface

1. **Game language** - select `pt` if the game is in Portuguese, `en` if in English. This controls which text the bot searches for on screen.

2. **Items to buy** - check which items the bot should buy: Mystic Medals, Covenant Bookmarks and/or Friendship Points (all checked by default). At least one must be selected; the selection is locked while the bot is running.

3. **Input mode** - choose between entering the number of Skystones to spend or the number of refreshes. The program calculates the equivalent automatically (3 Skystones = 1 refresh). Skystones input must be a multiple of 3.

4. **Start** - launches the bot. The Secret Shop must already be open before clicking.

5. **Stop** - asks the bot to stop. It finishes the action in progress (e.g. a purchase being confirmed) and stops before the next one, without completing the cycle. **Start** becomes available again only after the bot has actually stopped.

---

## Bot Flow

Each cycle performs the following steps:

1. Scans visible items on screen and buys the selected ones
2. Confirms each purchase in the confirmation dialog
3. Scrolls the list down and scans again
4. Clicks Refresh and confirms the renewal
5. Waits and repeats until the configured number of refreshes is reached; the shop shown after the last refresh is also scanned

Purchases and refreshes are only counted when their confirmation dialog is found. If the refresh fails several times in a row (`MAX_REFRESH_FAILURES` in `config.py`, e.g. when out of Skystones), the bot stops by itself. Errors are shown in the log, with the full traceback in the console.

Monitored items:

- Mystic Medals (50 per purchase, 280,000 gold each)
- Covenant Bookmarks (5 per purchase, 184,000 gold each)
- Friendship Points (50 per purchase, 18,000 gold each)

---

## Statistics

- Session start and end time
- Total duration
- Refreshes completed vs. total configured
- Total Covenant Bookmarks, Mystic Medals and Friendship Points purchased
- Total gold spent

---

## Files

| File | Description |
|---|---|
| `main.py` | Bot logic and graphical interface |
| `config.py` | Constants, strings, and language configuration |
| `tests/` | Regression tests (fake device and OCR, no emulator needed) |

---

## Tests

The tests use only the standard library (`unittest`) and do not need the emulator or Tesseract:

```bash
python -m unittest
```
