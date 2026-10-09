# Secret Shop Bot

A desktop bot that refreshes the **Secret Shop** in *Epic Seven* and automatically buys the items you choose (Mystic Medals, Covenant Bookmarks and Friendship Points), running the game on an Android emulator on Windows.

You tell it how many Skystones (or refreshes) to spend; it scans the shop, buys the selected items, refreshes, and repeats until the budget is used, showing live statistics and a log.

> **Use at your own risk.** Automating the game may break Epic Seven's terms of service and put your account at risk.

---

## How it works

The bot never reads the game's memory or network traffic. It works only with what is on screen, like a person would:

1. It takes a screenshot of the emulator through **ADB** (using [uiautomator2](https://github.com/openatx/uiautomator2)).
2. It reads the text on the screenshot with **Tesseract OCR** and looks for the item names and the buttons (`Comprar`/`Buy`, `Renovar`/`Refresh`, `Cancelar`/`Cancel`, `Confirmar`/`Confirm`).
3. It taps where it found them, also through ADB.

Because everything depends on reading the screen, the game must stay visible on the Secret Shop and you should not use the emulator while the bot is running.

---

## Requirements

- Windows 10 or later
- Python 3.13 or later
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) with the **Portuguese** (`por`) language pack
- An Android emulator with ADB enabled and Epic Seven installed

The bot was developed and tested with **MuMu Player** at a resolution of **1600x900**, with ADB at `127.0.0.1:7555`. Other emulators should work as long as ADB is reachable (see [Emulator and ADB](#3-emulator-and-adb)), but other resolutions have not been tested: a couple of fallback taps use fixed offsets that were tuned for 1600x900.

---

## Installation

### 1. Tesseract OCR

Download and install Tesseract for Windows from the [UB Mannheim builds](https://github.com/UB-Mannheim/tesseract/wiki). During installation, select the **Portuguese** language pack: the bot always reads the screen with it, **even when the game is in English**.

The program expects Tesseract at:

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

If you install it elsewhere, update this line near the top of `main.py`:

```python
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

### 2. Python and dependencies

From the project folder, create a virtual environment and install the pinned packages:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

| Package | Purpose |
| --- | --- |
| uiautomator2 | Screenshots and taps on the emulator via ADB |
| pytesseract | Text recognition (OCR) with Tesseract |
| pillow | Image handling for the screenshots |

The other packages in `requirements.txt` (adbutils, requests, etc.) are their dependencies. `adbutils` also ships its own `adb.exe`, so the bot does not need ADB on your `PATH`.

### 3. Emulator and ADB

Enable ADB in your emulator's settings. The bot connects to `127.0.0.1:7555`, the address of the MuMu Player setup it was tested with. Other emulators (and other MuMu versions) may use a different port, shown in the emulator's ADB settings. If yours is different, change this line in `bot_loop` in `main.py`:

```python
_device = u2.connect("127.0.0.1:7555")
```

To check the connection manually you need the `adb` command ([Android platform-tools](https://developer.android.com/tools/releases/platform-tools)):

```bash
adb connect 127.0.0.1:7555
adb devices
```

The emulator should be listed with the status `device`.

---

## Running

1. Open the emulator and the game, and go to the **Secret Shop** screen.
2. With the virtual environment active, run:

```bash
python main.py
```

---

## Using the interface

1. **Game language**: `pt` if the game is in Portuguese, `en` if it is in English. This sets which words the bot looks for on screen. The interface itself is always in English.
2. **Items to buy**: check the items the bot should buy (all checked by default). At least one must be selected, and the selection is locked while the bot is running.
3. **Skystones / Refreshes**: choose whether you are entering Skystones to spend or a number of refreshes. The program shows the equivalent (3 Skystones = 1 refresh). Skystones must be a multiple of 3.
4. **Start**: starts the bot. The Secret Shop must already be open.
5. **Stop**: asks the bot to stop. It finishes the action in progress (a purchase or refresh being confirmed, so no dialog is left open) and then stops, without completing the cycle. Pauses between cycles, the wait after scrolling and repeated searches for the Refresh button are cut short. **Start** is enabled again only after the bot has actually stopped.

---

## What the bot does

Each cycle:

1. Reads the shop and buys the selected items that are visible, confirming each purchase in its dialog.
2. Scrolls the list down, waits for it to settle and buys again.
3. Taps **Refresh** and confirms it.
4. Repeats until the configured number of refreshes is reached. The shop shown after the last refresh is also checked before the bot stops.

Rules that keep purchases and counts correct:

- **Only confirmed actions count.** A purchase or refresh is counted only when its confirmation dialog was found and confirmed.
- **No double purchases.** Items showing `0/1` (already bought in this shop) are skipped, and the bot remembers what it bought until a refresh really happens.
- **Right dialog.** The refresh is confirmed by tapping the `Confirmar`/`Confirm` button read on screen, which only the refresh dialog has. If it cannot be read, the bot falls back to tapping the button's usual position.
- **Retries.** Dialogs and the Refresh button are searched for in several screenshots, both in color and in grayscale (the refresh dialog is only readable in grayscale).
- **Leftover dialogs.** If a purchase dialog opens too late and stays on top of the shop, the bot closes it with Cancel as soon as it sees it.
- **Safe stop.** If refreshing fails several times in a row (for example, when you run out of Skystones), the bot stops by itself.

The log shows each step. Errors are also logged, with the full traceback printed in the console.

### Items

| Item | Per purchase | Price |
| --- | --- | --- |
| Mystic Medals | 50 | 280,000 gold |
| Covenant Bookmarks | 5 | 184,000 gold |
| Friendship Points | 50 | 18,000 gold |

Items are defined in the `ITEMS` table in `config.py` (names in both languages, price, quantity and statistics label). Adding an entry there is enough for the bot to look for it, list it under *Items to buy* and count it in the statistics.

---

## Statistics

- Session start and end time, and total duration
- Refreshes completed vs. configured
- Quantity and number of purchases for each item (Mystic Medals, Bookmarks, Friendship Points)
- Total gold spent

---

## Configuration

Settings in `config.py`:

| Setting | Default | What it does |
| --- | --- | --- |
| `ITEMS` | 3 items | Items the bot can buy (see [Items](#items)) |
| `SKYSTONES_PER_REFRESH` | `3` | Skystones spent per refresh, used to convert the input |
| `DIALOG_ATTEMPTS` | `3` | Screenshots taken when looking for a dialog or the Refresh button |
| `DIALOG_RETRY_DELAY` | `0.5` s | Wait between those screenshots |
| `SCROLL_SETTLE_DELAY` | `1.0` s | Wait after scrolling, so the list stops moving before it is read |
| `MAX_REFRESH_FAILURES` | `3` | Failed refreshes in a row before the bot stops |
| `ROW_TOLERANCE_PX` | `50` | How far apart vertically (px) an item name and its buttons can be and still count as the same row |
| `DEBUG_MAX_FILES` | `50` | Diagnostic screenshots kept (see [Troubleshooting](#troubleshooting)) |

The on-screen words the bot looks for (`REFRESH_STR`, `CANCEL_STR`, `BUY_STR`, `CONFIRM_STR`) and the log messages in both languages are also in `config.py`. The ADB address and the Tesseract path are in `main.py`, as described in [Installation](#installation).

---

## Troubleshooting

When the bot cannot find a dialog or the Refresh button, it saves the screenshot it analysed to `%TEMP%\secret_shop_bot` and shows the file path in the log. Only the latest `DEBUG_MAX_FILES` are kept. Opening these images is the fastest way to see what was on screen.

| Symptom | Likely cause and fix |
| --- | --- |
| `ConnectError: device 127.0.0.1:7555 not online` | The emulator is closed, ADB is disabled, or it uses another port. Start the emulator, enable ADB and check the address (see [Emulator and ADB](#3-emulator-and-adb)). |
| `TesseractNotFoundError` | Tesseract is not installed or is in another folder. Install it or update `tesseract_cmd` in `main.py`. |
| `'Renovar' button not found!` / `'Refresh' button not found!` | The shop was not on screen (another menu, popup or dialog was open). Check the saved screenshot and go back to the Secret Shop. |
| `Refresh dialog not found` | The refresh dialog did not open or was not read. A common cause is running out of Skystones. |
| `Confirmation dialog not found` | The purchase dialog did not open in time. The item is not counted and is tried again later. |
| The bot stops with `Refresh failed 3 times in a row` | The safe stop after repeated failures. Check the saved screenshots for the reason. |
| Wrong words are never found | Make sure **Game language** matches the game and that the Tesseract Portuguese pack is installed. |

Note: log messages follow the selected game language, so with `pt` they appear in Portuguese (for example, `Botão 'Renovar' não encontrado!`).

---

## Project files

| File | Description |
| --- | --- |
| `main.py` | Bot logic (screen reading, purchases, refreshes) and the graphical interface |
| `config.py` | Items, settings, on-screen words and log/interface texts |
| `tests/` | Automated tests with a simulated emulator and OCR |
| `requirements.txt` | Pinned Python dependencies |

---

## Tests

The tests use only the standard library (`unittest`) and do not need the emulator or Tesseract:

```bash
python -m unittest
```
