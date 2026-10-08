import threading
import tkinter as tk
import unittest
from unittest import mock

import main
from config import LOG


def _ocr_data(words, conf=None):
    """Monta um dict no formato de pytesseract.image_to_data a partir de (texto, x, y)."""
    return {
        'text': [w[0] for w in words],
        'conf': conf or [90] * len(words),
        'left': [w[1] - 5 for w in words],
        'top': [w[2] - 5 for w in words],
        'width': [10] * len(words),
        'height': [10] * len(words),
    }


class FakeDevice:
    """Simula a Loja Secreta: cada estado da loja tem Mystic Medals e abre janelas ao clicar."""

    BUY_BTN = (300, 100)
    REFRESH_BTN = (500, 900)
    BUY_CONFIRM = (600, 500)
    REFRESH_CONFIRM = (625, 625)  # w // 2 + 125, h // 2 + 125 com tela 1000x1000

    def __init__(self, buy_dialog=True, refresh_dialog=True, item="Mystic", refresh_gray_only=False,
                 buy_dialog_delay=0):
        self.buy_dialog = buy_dialog
        self.buy_dialog_delay = buy_dialog_delay  # leituras de OCR até a janela de compra aparecer
        self.dialog_reads = 0
        self.refresh_gray_only = refresh_gray_only
        self.item = item
        self.refresh_dialog = refresh_dialog
        self.shop = 0
        self.scanned = set()
        self.dialog = None
        self.bought = []
        self.refreshes = 0

    def screenshot(self):
        return self

    def window_size(self):
        return (1000, 1000)

    def swipe_ext(self, direction):
        pass

    def words(self, gray=False):
        if self.dialog == "refresh" and self.refresh_gray_only and not gray:
            return []
        if self.dialog == "buy":
            self.dialog_reads += 1
            if self.dialog_reads <= self.buy_dialog_delay:
                return []
            return [("Cancel", 400, 500), ("Buy", *self.BUY_CONFIRM)]
        if self.dialog == "refresh":
            return [("Cancel", 400, 600), ("Confirm", *self.REFRESH_CONFIRM)]
        self.scanned.add(self.shop)
        return [(self.item, 0, 100), ("Buy", *self.BUY_BTN), ("Refresh", *self.REFRESH_BTN)]

    def click(self, x, y):
        pos = (x, y)
        if self.dialog == "buy":
            if pos == self.BUY_CONFIRM:
                self.bought.append(self.shop)
            self.dialog = None
        elif self.dialog == "refresh":
            if pos == self.REFRESH_CONFIRM:
                self.shop += 1
                self.refreshes += 1
            self.dialog = None
        elif pos == self.BUY_BTN and self.buy_dialog:
            self.dialog = "buy"
            self.dialog_reads = 0
        elif pos == self.REFRESH_BTN and self.refresh_dialog:
            self.dialog = "refresh"


class BotTestCase(unittest.TestCase):
    def setUp(self):
        self.device = FakeDevice()
        patches = [
            mock.patch("main.time.sleep"),
            mock.patch.object(main, "_ocr", lambda dev, gray=False: _ocr_data(dev.words(gray))),
            mock.patch.object(main.u2, "connect", lambda addr: self.device),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def run_bot(self, max_refreshes, itens_idx=None):
        main.state.reset(max_refreshes)
        main.bot_loop("en", max_refreshes, itens_idx)
        return main.state.drain_logs()


class TestFindText(unittest.TestCase):
    def test_find_text_ignores_negative_confidence(self):
        data = _ocr_data([("Buy", 10, 10), ("Buy", 50, 60)], conf=[-1, 90])
        self.assertEqual(main._find_text(data, "buy"), (50, 60))

    def test_find_text_in_row_respects_tolerance_and_min_x(self):
        data = _ocr_data([("Buy", 100, 500), ("Buy", 300, 900), ("Buy", 600, 520)])
        self.assertEqual(main._find_text_in_row(data, "Buy", 500), (100, 500))
        self.assertEqual(main._find_text_in_row(data, "Buy", 500, min_x=400), (600, 520))
        self.assertIsNone(main._find_text_in_row(data, "Buy", 700))


class TestBotLoop(BotTestCase):
    def test_scans_shop_after_last_refresh(self):
        self.run_bot(3)
        self.assertEqual(self.device.scanned, {0, 1, 2, 3})
        self.assertEqual(self.device.refreshes, 3)
        self.assertEqual(main.state.refreshes_done, 3)

    def test_counts_only_confirmed_purchases(self):
        self.run_bot(3)
        self.assertEqual(len(self.device.bought), 4)
        self.assertEqual(main.state.mystic_buys, 4)
        self.assertEqual(main.state.gold_spent, 4 * main.MYSTIC_GOLD)

    def test_counts_friendship_points_purchases(self):
        self.device.item = "Friendship"
        self.run_bot(1)
        self.assertEqual(main.state.friendship_buys, 2)
        self.assertEqual(main.state.friendship_total, 2 * main.FRIENDSHIP_AMOUNT)
        self.assertEqual(main.state.gold_spent, 2 * main.FRIENDSHIP_GOLD)
        self.assertEqual(main.state.mystic_buys, 0)

    def test_skips_unselected_items(self):
        logs = self.run_bot(1, [main.BOOKMARK_IDX, main.FRIENDSHIP_IDX])
        self.assertEqual(self.device.bought, [])
        self.assertEqual(main.state.mystic_buys, 0)
        self.assertTrue(any("Covenant Bookmarks, Friendship Points" in line for line in logs))

    def test_purchase_without_dialog_is_not_counted(self):
        self.device.buy_dialog = False
        self.run_bot(2)
        self.assertEqual(self.device.bought, [])
        self.assertEqual(main.state.mystic_buys, 0)
        self.assertEqual(main.state.gold_spent, 0)

    def test_waits_for_slow_purchase_dialog(self):
        self.device.buy_dialog_delay = 2  # some na 1ª tentativa (leitura colorida + cinza)
        self.run_bot(1)
        self.assertEqual(main.state.mystic_buys, 2)

    def test_closes_stray_dialog_before_refreshing(self):
        self.device.buy_dialog_delay = 2 * main.DIALOG_ATTEMPTS  # aparece só depois que o bot desistiu
        logs = self.run_bot(2)
        self.assertEqual(main.state.mystic_buys, 0)
        self.assertEqual(main.state.refreshes_done, 2)
        self.assertTrue(any(LOG["en"]["dialog_closed"] in line for line in logs))

    def test_refresh_dialog_read_only_in_grayscale(self):
        self.device.refresh_gray_only = True
        self.run_bot(2)
        self.assertEqual(self.device.refreshes, 2)
        self.assertEqual(main.state.refreshes_done, 2)

    def test_stops_after_repeated_refresh_failures(self):
        self.device.refresh_dialog = False
        logs = self.run_bot(5)
        self.assertEqual(main.state.refreshes_done, 0)
        expected = LOG["en"]["refresh_aborted"].format(main.MAX_REFRESH_FAILURES)
        self.assertTrue(any(expected in line for line in logs))

    def test_exception_is_logged_and_end_time_set(self):
        with mock.patch.object(main.u2, "connect", side_effect=ConnectionError("adb offline")), \
                mock.patch("main.traceback.print_exc"):
            logs = self.run_bot(1)
        self.assertIsNotNone(main.state.end_time)
        self.assertTrue(any("ConnectionError: adb offline" in line for line in logs))


class TestApp(BotTestCase):
    def setUp(self):
        super().setUp()
        try:
            self.app = main.App()
        except tk.TclError as e:
            self.skipTest(f"Tk indisponível: {e}")
        self.app.withdraw()
        self.addCleanup(self.app.destroy)

    def test_stop_keeps_start_disabled_until_bot_ends(self):
        gate = threading.Event()
        ocr = main._ocr

        def blocking_ocr(dev, gray=False):
            gate.wait()
            return ocr(dev, gray)

        with mock.patch.object(main, "_ocr", blocking_ocr):
            self.app.input_var.set("30")
            self.app._on_start()
            thread = self.app._bot_thread
            assert thread is not None

            self.app._on_stop()
            self.assertEqual(str(self.app.btn_start["state"]), "disabled")

            self.app._on_start()
            self.assertIs(self.app._bot_thread, thread)

            gate.set()
            thread.join(5)
        self.assertFalse(thread.is_alive())
        self.app._poll()
        self.assertEqual(str(self.app.btn_start["state"]), "normal")

    def test_start_requires_at_least_one_item(self):
        for var in self.app.item_vars:
            var.set(False)
        self.app.input_var.set("30")
        self.app._on_start()
        self.assertIsNone(self.app._bot_thread)
        self.assertEqual(self.app.lbl_error["text"], main._UI["no_items"])

    def test_start_buys_only_selected_items(self):
        self.app.item_vars[main.MYSTIC_IDX].set(False)
        self.app.input_var.set("3")
        self.app._on_start()
        thread = self.app._bot_thread
        assert thread is not None
        self.assertTrue(all(str(c["state"]) == "disabled" for c in self.app._item_checks))

        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(self.device.bought, [])
        self.assertEqual(main.state.mystic_buys, 0)

        self.app._poll()
        self.assertTrue(all(str(c["state"]) == "normal" for c in self.app._item_checks))


if __name__ == "__main__":
    unittest.main()
