import tempfile
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, scrolledtext

import uiautomator2 as u2
import pytesseract
from PIL import ImageOps

from config import (
    SKYSTONES_PER_REFRESH,
    BOOKMARK_AMOUNT, MYSTIC_AMOUNT, FRIENDSHIP_AMOUNT,
    BOOKMARK_GOLD, MYSTIC_GOLD, FRIENDSHIP_GOLD,
    MYSTIC_IDX, BOOKMARK_IDX, FRIENDSHIP_IDX,
    DIALOG_ATTEMPTS, DIALOG_RETRY_DELAY, MAX_REFRESH_FAILURES, ROW_TOLERANCE_PX,
    ITENS, REFRESH_STR, CANCEL_STR, BUY_STR, SOLD_OUT_STR,
    LOG, UI,
)

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

_UI_LANG = "en"
_UI = UI[_UI_LANG]
DEBUG_DIR = Path(tempfile.gettempdir()) / "secret_shop_bot"


class BotState:
    def __init__(self):
        self.stop_event = threading.Event()
        self.start_time = None
        self.end_time = None
        self.refreshes_done = 0
        self.max_refreshes = 0
        self.bookmark_buys = 0
        self.mystic_buys = 0
        self.friendship_buys = 0
        self.gold_spent = 0
        self._log = []
        self._lock = threading.Lock()

    def reset(self, max_refreshes: int):
        self.stop_event.clear()
        self.start_time = datetime.now()
        self.end_time = None
        self.refreshes_done = 0
        self.max_refreshes = max_refreshes
        self.bookmark_buys = 0
        self.mystic_buys = 0
        self.friendship_buys = 0
        self.gold_spent = 0
        with self._lock:
            self._log = []

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        with self._lock:
            self._log.append(f"[{ts}] {msg}")

    def drain_logs(self) -> list:
        with self._lock:
            out, self._log = self._log[:], []
            return out

    @property
    def bookmarks_total(self):
        return self.bookmark_buys * BOOKMARK_AMOUNT

    @property
    def mystics_total(self):
        return self.mystic_buys * MYSTIC_AMOUNT

    @property
    def friendship_total(self):
        return self.friendship_buys * FRIENDSHIP_AMOUNT


state = BotState()
_device = None


def _screenshot():
    return _device.screenshot()


def _ocr(img, gray: bool = False) -> dict:
    if gray:
        img = ImageOps.grayscale(img)
    return pytesseract.image_to_data(img, lang='por', output_type=pytesseract.Output.DICT)


def _word_center(data: dict, i: int):
    return data['left'][i] + data['width'][i] // 2, data['top'][i] + data['height'][i] // 2


def _find_text(data: dict, text: str):
    tl = text.lower()
    for i, word in enumerate(data['text']):
        if data['conf'][i] < 0:
            continue
        if tl in word.lower():
            return _word_center(data, i)
    return None


def _find_text_in_row(data: dict, text: str, y: int, min_x: int | None = None):
    tl = text.lower()
    for i, word in enumerate(data['text']):
        if tl in word.lower():
            wx, wy = _word_center(data, i)
            if abs(wy - y) < ROW_TOLERANCE_PX and (min_x is None or wx > min_x):
                return wx, wy
    return None


def _wait_for_text(text: str, attempts: int = DIALOG_ATTEMPTS):
    data = {}
    for attempt in range(attempts):
        if attempt:
            time.sleep(DIALOG_RETRY_DELAY)
        img = _screenshot()
        # A janela de renovação (texto claro sobre azul) só é lida em tons de cinza,
        # que por sua vez perdem textos da loja; por isso o cinza é só segunda tentativa.
        for gray in (False, True):
            data = _ocr(img, gray)
            pos = _find_text(data, text)
            if pos:
                return pos, data
    return None, data


def _save_debug_screenshot(idioma: str, reason: str):
    DEBUG_DIR.mkdir(exist_ok=True)
    path = DEBUG_DIR / f"{datetime.now():%Y%m%d-%H%M%S}-{reason}.png"
    _screenshot().save(path)
    state.log(LOG[idioma]["debug_saved"].format(path))


def _close_stray_dialog(idioma: str, data: dict | None = None) -> bool:
    if data is not None:
        cancel_pos = _find_text(data, CANCEL_STR[idioma])
    else:
        cancel_pos, _ = _wait_for_text(CANCEL_STR[idioma], attempts=1)
    if not cancel_pos:
        return False
    state.log(LOG[idioma]["dialog_closed"])
    _device.click(*cancel_pos)
    time.sleep(1)
    return True


def _confirm_purchase(idioma: str) -> bool:
    lg = LOG[idioma]
    time.sleep(0.5)
    cancel_pos, data = _wait_for_text(CANCEL_STR[idioma])
    if not cancel_pos:
        state.log(lg["no_dialog"])
        _save_debug_screenshot(idioma, "no_dialog")
        return False
    confirm_pos = _find_text_in_row(data, BUY_STR[idioma], cancel_pos[1], min_x=cancel_pos[0])
    if confirm_pos:
        state.log(lg["confirming"].format(*confirm_pos))
        _device.click(*confirm_pos)
        return True
    state.log(lg["no_confirm_btn"])
    _device.click(*cancel_pos)
    return False


def _buy_item(pos, data: dict, item_idx: int, idioma: str) -> bool:
    lg = LOG[idioma]
    buy_pos = _find_text_in_row(data, BUY_STR[idioma], pos[1])
    if buy_pos:
        _device.click(*buy_pos)
    else:
        state.log(lg["no_buy_ocr"])
        _device.click(pos[0] + 160, pos[1])

    confirmed = _confirm_purchase(idioma)
    time.sleep(0.5)
    if not confirmed:
        return False

    with state._lock:
        if item_idx == MYSTIC_IDX:
            state.mystic_buys += 1
            state.gold_spent += MYSTIC_GOLD
        elif item_idx == BOOKMARK_IDX:
            state.bookmark_buys += 1
            state.gold_spent += BOOKMARK_GOLD
        elif item_idx == FRIENDSHIP_IDX:
            state.friendship_buys += 1
            state.gold_spent += FRIENDSHIP_GOLD
    return True


def _buy_all_visible(itens: list[tuple[int, str]], already_bought: set, idioma: str) -> set:
    lg = LOG[idioma]
    newly = set()
    for idx, item in itens:
        if item in already_bought or state.stop_event.is_set():
            continue
        data = _ocr(_screenshot())
        pos = _find_text(data, item.split()[0])
        if not pos:
            continue
        if _find_text_in_row(data, SOLD_OUT_STR, pos[1]):
            state.log(lg["sold_out"].format(item))
            newly.add(item)
            continue
        state.log(lg["item_found"].format(item))
        if _buy_item(pos, data, idx, idioma):
            newly.add(item)
    return newly


def _refresh_shop(idioma: str) -> bool:
    lg = LOG[idioma]
    pos, data = _wait_for_text(REFRESH_STR[idioma])
    # Uma janela de compra que abriu depois que o bot desistiu dela fica por cima da loja:
    # primeiro olha a leitura que já foi feita; sem Renovar, faz uma busca completa.
    if _close_stray_dialog(idioma, data) or (not pos and _close_stray_dialog(idioma)):
        pos, _ = _wait_for_text(REFRESH_STR[idioma])
    if not pos:
        state.log(lg["no_refresh_btn"].format(REFRESH_STR[idioma]))
        _save_debug_screenshot(idioma, "no_refresh_btn")
        return False
    state.log(lg["refreshing"].format(pos))
    _device.click(*pos)
    time.sleep(1.5)
    if not _wait_for_text(CANCEL_STR[idioma])[0]:
        state.log(lg["no_refresh_dialog"])
        _save_debug_screenshot(idioma, "no_refresh_dialog")
        return False
    w, h = _device.window_size()
    _device.click(w // 2 + 125, h // 2 + 125)
    with state._lock:
        state.refreshes_done += 1
    return True


def bot_loop(idioma: str, max_refreshes: int, itens_idx: list[int] | None = None):
    global _device
    lg = LOG[idioma]
    itens = [
        (idx, item) for idx, item in enumerate(ITENS[idioma])
        if itens_idx is None or idx in itens_idx
    ]

    try:
        state.log(lg["targets"].format(", ".join(item for _, item in itens)))
        state.log(lg["connecting"])
        _device = u2.connect("127.0.0.1:7555")
        state.log(lg["connected"])

        ciclo = 1
        refresh_failures = 0
        bought = set()  # itens já comprados na loja atual; só zera quando a renovação acontece
        while not state.stop_event.is_set():
            state.log(lg["cycle"].format(ciclo))

            bought |= _buy_all_visible(itens, bought, idioma)
            if state.stop_event.is_set():
                break

            state.log(lg["scrolling"])
            _device.swipe_ext("up")
            time.sleep(0.5)

            bought |= _buy_all_visible(itens, bought, idioma)
            if state.stop_event.is_set():
                break

            if state.refreshes_done >= max_refreshes:
                state.log(lg["max_reached"])
                break

            if _refresh_shop(idioma):
                refresh_failures = 0
                bought = set()
            else:
                refresh_failures += 1
                if refresh_failures >= MAX_REFRESH_FAILURES:
                    state.log(lg["refresh_aborted"].format(refresh_failures))
                    break
            ciclo += 1
            time.sleep(2)
    except Exception as e:
        traceback.print_exc()
        state.log(lg["error"].format(f"{type(e).__name__}: {e}"))
    finally:
        with state._lock:
            state.end_time = datetime.now()
        state.log(lg["bot_stopped"])


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(_UI["title"])
        self.resizable(False, False)

        self.lang_var = tk.StringVar(value="pt")
        self.mode_var = tk.StringVar(value="sky")
        self.input_var = tk.StringVar()
        self.item_vars = [tk.BooleanVar(value=True) for _ in ITENS[_UI_LANG]]
        self._bot_thread = None

        self._build()
        self._poll()

    def _build(self):
        pad = {"padx": 10, "pady": 6}

        left = tk.LabelFrame(self, text="Configuration", **pad)
        left.grid(row=0, column=0, sticky="nsew", **pad)

        tk.Label(left, text=_UI["lang_label"]).grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            left, textvariable=self.lang_var,
            values=["pt", "en"], state="readonly", width=5,
        ).grid(row=0, column=1, sticky="w", pady=4)

        items_frame = tk.LabelFrame(left, text=_UI["items_label"], padx=6)
        items_frame.grid(row=1, column=0, columnspan=2, sticky="we", pady=4)
        self._item_checks = []
        for item, var in zip(ITENS[_UI_LANG], self.item_vars, strict=True):
            check = tk.Checkbutton(
                items_frame, text=item, variable=var, command=self._on_input_change,
            )
            check.pack(anchor="w")
            self._item_checks.append(check)

        tk.Radiobutton(
            left, text=_UI["mode_sky"],
            variable=self.mode_var, value="sky",
            command=self._on_input_change,
        ).grid(row=2, column=0, columnspan=2, sticky="w")

        tk.Radiobutton(
            left, text=_UI["mode_ref"],
            variable=self.mode_var, value="ref",
            command=self._on_input_change,
        ).grid(row=3, column=0, columnspan=2, sticky="w")

        tk.Entry(left, textvariable=self.input_var, width=12).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=4
        )
        self.input_var.trace_add("write", lambda *_: self._on_input_change())

        self.lbl_hint = tk.Label(left, fg="gray")
        self.lbl_hint.grid(row=5, column=0, columnspan=2, sticky="w")

        self.lbl_error = tk.Label(left, fg="red")
        self.lbl_error.grid(row=6, column=0, columnspan=2, sticky="w")

        btn_frame = tk.Frame(left)
        btn_frame.grid(row=7, column=0, columnspan=2, pady=8)

        self.btn_start = tk.Button(
            btn_frame, text=_UI["btn_start"], width=10,
            bg="#4CAF50", fg="white", command=self._on_start,
        )
        self.btn_start.pack(side="left", padx=4)

        self.btn_stop = tk.Button(
            btn_frame, text=_UI["btn_stop"], width=10,
            bg="#f44336", fg="white", state="disabled", command=self._on_stop,
        )
        self.btn_stop.pack(side="left", padx=4)

        right = tk.LabelFrame(self, text="Statistics", **pad)
        right.grid(row=0, column=1, sticky="nsew", **pad)

        self._stat_labels = {}
        rows = [
            ("lbl_start", "val_start"),
            ("lbl_end", "val_end"),
            ("lbl_duration", "val_duration"),
            None,
            ("lbl_refreshes", "val_refreshes"),
            ("lbl_bookmarks", "val_bookmarks"),
            ("lbl_mystics", "val_mystics"),
            ("lbl_friendship", "val_friendship"),
            ("lbl_gold", "val_gold"),
        ]
        for r, entry in enumerate(rows):
            if entry is None:
                tk.Frame(right, height=6).grid(row=r, column=0)
            else:
                lk, vk = entry
                tk.Label(right, text=_UI[lk], anchor="w").grid(row=r, column=0, sticky="w", pady=2)
                val = tk.Label(right, text="--", anchor="w", width=26)
                val.grid(row=r, column=1, sticky="w")
                self._stat_labels[vk] = val

        log_frame = tk.LabelFrame(self, text="Log", **pad)
        log_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", **pad)
        self.log_box = scrolledtext.ScrolledText(
            log_frame, height=12, width=72, state="disabled", wrap="word",
        )
        self.log_box.pack(fill="both", expand=True)

    def _stat(self, key: str, value: str):
        self._stat_labels[key].config(text=value)

    def _on_input_change(self, *_):
        self.lbl_error.config(text="")
        raw = self.input_var.get().strip()
        mode = self.mode_var.get()
        hint = ""
        try:
            val = int(raw) if raw else 0
            hint = (
                f"= {val // SKYSTONES_PER_REFRESH} {_UI['sky_hint']}"
                if mode == "sky"
                else f"= {val * SKYSTONES_PER_REFRESH} {_UI['ref_hint']}"
            )
        except ValueError:
            pass
        self.lbl_hint.config(text=hint)

    def _validate(self):
        raw = self.input_var.get().strip()
        try:
            val = int(raw)
            if val <= 0:
                raise ValueError
        except ValueError:
            self.lbl_error.config(text=_UI["invalid_val"])
            return None
        if self.mode_var.get() == "sky":
            if val % SKYSTONES_PER_REFRESH != 0:
                self.lbl_error.config(text=_UI["invalid_mult"])
                return None
            return val // SKYSTONES_PER_REFRESH
        return val

    def _set_running(self, running: bool):
        self.btn_start.config(state="disabled" if running else "normal")
        self.btn_stop.config(state="normal" if running else "disabled")
        for check in self._item_checks:
            check.config(state="disabled" if running else "normal")

    def _on_start(self):
        if self._bot_thread and self._bot_thread.is_alive():
            return
        itens_idx = [i for i, var in enumerate(self.item_vars) if var.get()]
        if not itens_idx:
            self.lbl_error.config(text=_UI["no_items"])
            return
        max_ref = self._validate()
        if max_ref is None:
            return
        state.reset(max_ref)
        self._set_running(True)
        self._bot_thread = threading.Thread(
            target=bot_loop, args=(self.lang_var.get(), max_ref, itens_idx), daemon=True,
        )
        self._bot_thread.start()

    def _on_stop(self):
        state.stop_event.set()
        self.btn_stop.config(state="disabled")

    def _poll(self):
        s = state

        def fmt_time(dt):
            return dt.strftime("%H:%M:%S") if dt else "--:--:--"

        def fmt_duration():
            if not s.start_time:
                return "--:--:--"
            sec = int(((s.end_time or datetime.now()) - s.start_time).total_seconds())
            h, r = divmod(sec, 3600)
            m, s2 = divmod(r, 60)
            return f"{h:02d}:{m:02d}:{s2:02d}"

        self._stat("val_start", fmt_time(s.start_time))
        self._stat("val_end", fmt_time(s.end_time))
        self._stat("val_duration", fmt_duration())
        self._stat("val_refreshes", f"{s.refreshes_done} / {s.max_refreshes}")
        self._stat("val_bookmarks", f"{s.bookmarks_total} ({s.bookmark_buys} {_UI['purchases']})")
        self._stat("val_mystics", f"{s.mystics_total} ({s.mystic_buys} {_UI['purchases']})")
        self._stat("val_friendship", f"{s.friendship_total} ({s.friendship_buys} {_UI['purchases']})")
        self._stat("val_gold", f"{s.gold_spent:,}".replace(",", "."))

        for msg in s.drain_logs():
            self.log_box.config(state="normal")
            self.log_box.insert("end", msg + "\n")
            self.log_box.see("end")
            self.log_box.config(state="disabled")

        if self._bot_thread and not self._bot_thread.is_alive():
            self._bot_thread = None
            self._set_running(False)

        self.after(500, self._poll)


if __name__ == "__main__":
    App().mainloop()
