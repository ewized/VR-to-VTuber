import os
import tempfile
import threading
import tkinter as tk
import unittest
from unittest.mock import patch

import bridge.settings as settings
import bridge.state as state
from bridge.ui import App


class AddressFormTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        settings_patch = patch.object(
            settings, "PATH", os.path.join(self.tmp.name, "settings.json")
        )
        settings_patch.start()
        self.addCleanup(settings_patch.stop)
        self.addCleanup(setattr, state, "loaded", False)
        self.addCleanup(state.stop_event.clear)
        settings.load()
        with patch.object(App, "_check_update"):
            try:
                self.app = App()
            except tk.TclError as exc:
                self.skipTest(f"A desktop display is required: {exc}")
        self.addCleanup(self.close_app)
        self.app.update()

    def close_app(self):
        """Cancel scheduled callbacks before destroying each test window."""
        for callback in self.app.tk.call("after", "info"):
            self.app.after_cancel(callback)
        self.app.destroy()

    def test_vtube_address_is_visible_before_start_and_survives_switching(self):
        self.assertTrue(self.app.vts_endpoint.winfo_ismapped())
        self.assertEqual(str(self.app.vts_host_entry["state"]), "normal")
        self.app.vts_host_var.set("stream-pc")
        self.app.vts_port_var.set("8002")
        self.app.choose("ifm")
        self.app.update()
        self.assertFalse(self.app.vts_endpoint.winfo_ismapped())
        self.app.choose("vts")
        self.app.update()
        self.assertEqual(self.app.vts_host_var.get(), "stream-pc")
        self.assertEqual(self.app.vts_port_var.get(), "8002")

    def test_invalid_address_prevents_starting_worker(self):
        for host, port in (("", "8001"), ("stream-pc", "0")):
            with (
                self.subTest(host=host, port=port),
                patch("bridge.ui.threading.Thread") as worker,
            ):
                self.app.vts_host_var.set(host)
                self.app.vts_port_var.set(port)
                self.app.start_btn.invoke()
                worker.assert_not_called()
                self.assertFalse(self.app.running)
                self.assertTrue(self.app.vts_endpoint_error.get())

    def test_start_uses_entered_address_and_stop_allows_editing(self):
        self.app.vts_host_var.set("stream-pc")
        self.app.vts_port_var.set("8002")
        ready = threading.Event()

        def run_bridge():
            state.stop_event.clear()
            ready.set()
            state.stop_event.wait(timeout=5)

        with (
            patch("bridge.runner.main", side_effect=run_bridge),
            patch("bridge.ui.recenter"),
        ):
            self.app.start_btn.invoke()
            try:
                self.assertTrue(ready.wait(timeout=2))
                self.assertEqual((state.vts_host, state.vts_port), ("stream-pc", 8002))
                self.assertEqual(str(self.app.vts_host_entry["state"]), "disabled")
                self.assertEqual(str(self.app.vts_port_entry["state"]), "disabled")
            finally:
                self.app.stop_btn.invoke()
                self.app.worker.join(timeout=2)
        self.assertEqual(str(self.app.vts_host_entry["state"]), "normal")
        self.assertEqual(str(self.app.vts_port_entry["state"]), "normal")


if __name__ == "__main__":
    unittest.main()
