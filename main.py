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
    DIALOG_ATTEMPTS, DIALOG_RETRY_DELAY, SCROLL_SETTLE_DELAY, MAX_REFRESH_FAILURES, ROW_TOLERANCE_PX, DEBUG_MAX_FILES,
    ITEMS, REFRESH_STR, CANCEL_STR, BUY_STR, SOLD_OUT_STR,
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
        self.buys = {item["key"]: 0 for item in ITEMS}
        self.gold_spent = 0
        self._log = []
        self._lock = threading.Lock()

    def reset(self, max_refreshes: int):
        self.stop_event.clear()
        self.start_time = datetime.now()
        self.end_time = None
        self.refreshes_done = 0
        self.max_refreshes = max_refreshes
        self.buys = {item["key"]: 0 for item in ITEMS}
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
    """Procura o texto em até `attempts` prints; devolve (posição, leitura, imagem analisada)."""
    data, img = {}, None
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
                return pos, data, img
    return None, data, img


def _save_debug_screenshot(idioma: str, reason: str, img=None):
    # Diagnóstico não pode derrubar o bot: uma falha ao salvar só vai para o log.
    # Salva a imagem que o OCR analisou (um print novo pode já mostrar outra tela).
    try:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
        path = DEBUG_DIR / f"{stamp}-{reason}.png"
        (img if img is not None else _screenshot()).save(path)
        for old in sorted(DEBUG_DIR.glob("*.png"))[:-DEBUG_MAX_FILES]:
            old.unlink()
    except Exception as e:
        state.log(LOG[idioma]["debug_failed"].format(f"{type(e).__name__}: {e}"))
        return
    state.log(LOG[idioma]["debug_saved"].format(path))


def _close_stray_dialog(idioma: str, data: dict | None = None) -> bool:
    if data is not None:
        cancel_pos = _find_text(data, CANCEL_STR[idioma])
    else:
        cancel_pos, _, _ = _wait_for_text(CANCEL_STR[idioma], attempts=1)
    if not cancel_pos:
        return False
    state.log(LOG[idioma]["dialog_closed"])
    _device.click(*cancel_pos)
    time.sleep(1)
    return True


def _confirm_purchase(idioma: str) -> bool:
    lg = LOG[idioma]
    time.sleep(0.5)
    cancel_pos, data, img = _wait_for_text(CANCEL_STR[idioma])
    if not cancel_pos:
        state.log(lg["no_dialog"])
        _save_debug_screenshot(idioma, "no_dialog", img)
        return False
    confirm_pos = _find_text_in_row(data, BUY_STR[idioma], cancel_pos[1], min_x=cancel_pos[0])
    if confirm_pos:
        state.log(lg["confirming"].format(*confirm_pos))
        _device.click(*confirm_pos)
        return True
    state.log(lg["no_confirm_btn"])
    _device.click(*cancel_pos)
    return False


def _buy_item(pos, data: dict, item: dict, idioma: str) -> bool:
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
        state.buys[item["key"]] += 1
        state.gold_spent += item["gold"]
    return True


def _buy_all_visible(itens: list[dict], already_bought: set, idioma: str) -> set:
    lg = LOG[idioma]
    newly = set()
    data = None  # a mesma leitura serve para todos os itens até o bot clicar em algo
    for item in itens:
        if item["key"] in already_bought or state.stop_event.is_set():
            continue
        name = item["name"][idioma]
        if data is None:
            data = _ocr(_screenshot())
        pos = _find_text(data, name.split()[0])
        if not pos:
            continue
        if _find_text_in_row(data, SOLD_OUT_STR, pos[1]):
            state.log(lg["sold_out"].format(name))
            newly.add(item["key"])
            continue
        state.log(lg["item_found"].format(name))
        if _buy_item(pos, data, item, idioma):
            newly.add(item["key"])
        data = None  # houve clique: a tela mudou
    return newly


def _refresh_shop(idioma: str) -> bool:
    lg = LOG[idioma]
    pos, data, img = _wait_for_text(REFRESH_STR[idioma])
    # Uma janela de compra que abriu depois que o bot desistiu dela fica por cima da loja:
    # primeiro olha a leitura que já foi feita; sem Renovar, faz uma busca completa.
    if _close_stray_dialog(idioma, data) or (not pos and _close_stray_dialog(idioma)):
        pos, _, img = _wait_for_text(REFRESH_STR[idioma])
    if not pos:
        state.log(lg["no_refresh_btn"].format(REFRESH_STR[idioma]))
        _save_debug_screenshot(idioma, "no_refresh_btn", img)
        return False
    state.log(lg["refreshing"].format(pos))
    _device.click(*pos)
    time.sleep(1.5)
    found, _, img = _wait_for_text(CANCEL_STR[idioma])
    if not found:
        state.log(lg["no_refresh_dialog"])
        _save_debug_screenshot(idioma, "no_refresh_dialog", img)
        return False
    w, h = _device.window_size()
    _device.click(w // 2 + 125, h // 2 + 125)
    with state._lock:
        state.refreshes_done += 1
    return True


def bot_loop(idioma: str, max_refreshes: int, item_keys: list[str] | None = None):
    global _device
    lg = LOG[idioma]
    itens = [item for item in ITEMS if item_keys is None or item["key"] in item_keys]

    try:
        state.log(lg["targets"].format(", ".join(item["name"][idioma] for item in itens)))
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
            time.sleep(SCROLL_SETTLE_DELAY)

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
        self.item_vars = {item["key"]: tk.BooleanVar(value=True) for item in ITEMS}
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
        for item in ITEMS:
            check = tk.Checkbutton(
                items_frame, text=item["name"][_UI_LANG], variable=self.item_vars[item["key"]],
                command=self._on_input_change,
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
            (_UI["lbl_start"], "val_start"),
            (_UI["lbl_end"], "val_end"),
            (_UI["lbl_duration"], "val_duration"),
            None,
            (_UI["lbl_refreshes"], "val_refreshes"),
            *((item["stat_label"][_UI_LANG], f"val_{item['key']}") for item in ITEMS),
            (_UI["lbl_gold"], "val_gold"),
        ]
        for r, entry in enumerate(rows):
            if entry is None:
                tk.Frame(right, height=6).grid(row=r, column=0)
            else:
                label, vk = entry
                tk.Label(right, text=label, anchor="w").grid(row=r, column=0, sticky="w", pady=2)
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
        item_keys = [key for key, var in self.item_vars.items() if var.get()]
        if not item_keys:
            self.lbl_error.config(text=_UI["no_items"])
            return
        max_ref = self._validate()
        if max_ref is None:
            return
        state.reset(max_ref)
        self._set_running(True)
        self._bot_thread = threading.Thread(
            target=bot_loop, args=(self.lang_var.get(), max_ref, item_keys), daemon=True,
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
        for item in ITEMS:
            buys = s.buys[item["key"]]
            self._stat(f"val_{item['key']}", f"{buys * item['amount']} ({buys} {_UI['purchases']})")
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
