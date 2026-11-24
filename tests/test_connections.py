import asyncio
import json
import os
import socket
import tempfile
import unittest
from unittest.mock import patch

import websockets

import bridge.settings as settings
import bridge.state as state
from bridge.face import RANGES
from bridge.outputs import vtube


class EndpointSettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        path = os.path.join(self.tmp.name, "bridge_settings.json")
        self.path_patch = patch.object(settings, "PATH", path)
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)
        self.addCleanup(setattr, state, "loaded", False)
        settings.load()

    def test_existing_settings_keep_local_vtube_studio_default(self):
        with open(settings.PATH, "w", encoding="utf-8") as handle:
            json.dump({"ifm_host": "old-receiver", "ifm_port": 49984}, handle)
        state.vts_host = "previous-pc"
        state.vts_port = 9001
        settings.load()
        self.assertEqual((state.vts_host, state.vts_port), ("127.0.0.1", 8001))
        self.assertEqual((state.ifm_host, state.ifm_port), ("old-receiver", 49984))

    def test_addresses_survive_save_reload_and_output_switches(self):
        for host in (
            "192.0.2.10",
            "stream-pc",
            "stream-pc.example",
            "localhost",
            "2001:db8::10",
        ):
            with self.subTest(host=host):
                settings.read_vts_endpoint(f"  {host}  ", " 8002 ")
                settings.save()
                settings.set_destination("ifm")
                settings.set_destination("vts")
                settings.load()
                self.assertEqual((state.vts_host, state.vts_port), (host, 8002))
                self.assertEqual((state.ifm_host, state.ifm_port), ("127.0.0.1", 49983))

    def test_bracketed_ipv6_is_stored_without_url_brackets(self):
        settings.read_vts_endpoint("[::1]", "8001")
        self.assertEqual(state.vts_host, "::1")

    def test_blank_address_uses_and_remembers_localhost(self):
        for host in ("", "   "):
            with self.subTest(host=host):
                settings.read_vts_endpoint(host, "8002")
                settings.save()
                settings.load()
                self.assertEqual((state.vts_host, state.vts_port), ("127.0.0.1", 8002))

    def test_malformed_saved_endpoint_keeps_defaults(self):
        for host, port in ((42, 8001), ("stream-pc", "invalid")):
            with self.subTest(host=host, port=port):
                with open(settings.PATH, "w", encoding="utf-8") as handle:
                    json.dump({"vts_host": host, "vts_port": port}, handle)
                settings.load()
                self.assertEqual((state.vts_host, state.vts_port), ("127.0.0.1", 8001))

    def test_invalid_address_or_port_changes_neither_value(self):
        settings.read_vts_endpoint("stream-pc", "8002")
        cases = (
            ("a b", "8001"),
            ("ws://stream-pc", "8001"),
            ("stream-pc:8001", "8001"),
            ("stream-pc/path", "8001"),
            ("[stream-pc]", "8001"),
            ("other-pc", ""),
            ("other-pc", "abc"),
            ("other-pc", "0"),
            ("other-pc", "65536"),
        )
        for host, port in cases:
            with self.subTest(host=host, port=port):
                with self.assertRaises(ValueError):
                    settings.read_vts_endpoint(host, port)
                self.assertEqual((state.vts_host, state.vts_port), ("stream-pc", 8002))


class VTubeConnectionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.token_patch = patch.object(
            vtube, "TOKEN_PATH", os.path.join(self.tmp.name, "token.json")
        )
        self.token_patch.start()
        self.addCleanup(self.token_patch.stop)
        self.addCleanup(state.stop_event.clear)
        state.stop_event.clear()
        state.destination = "vts"
        state.model_params = {}
        state.reset_outputs(RANGES)

    async def check_connection(self, host, bind_host):
        """Exercise authentication and tracking against a local VTube API receiver."""
        messages = []

        async def receiver(ws):
            async for raw in ws:
                message = json.loads(raw)
                kind = message["messageType"]
                messages.append(kind)
                if kind == "AuthenticationTokenRequest":
                    await ws.send(
                        json.dumps({"data": {"authenticationToken": "test-token"}})
                    )
                elif kind == "AuthenticationRequest":
                    self.assertEqual(
                        message["data"]["authenticationToken"], "test-token"
                    )
                    await ws.send(json.dumps({"data": {"authenticated": True}}))
                elif kind == "InjectParameterDataRequest":
                    self.assertTrue(message["data"]["parameterValues"])
                    state.stop_event.set()

        async with websockets.serve(receiver, bind_host, 0) as server:
            port = server.sockets[0].getsockname()[1]
            settings.read_vts_endpoint(host, port)
            await asyncio.wait_for(vtube.session(), timeout=5)
        self.assertEqual(state.status["output"], "Connected")
        self.assertIn("AuthenticationTokenRequest", messages)
        self.assertIn("AuthenticationRequest", messages)
        self.assertIn("InjectParameterDataRequest", messages)

    async def test_connects_and_sends_tracking_to_entered_ipv4_address(self):
        await self.check_connection("127.0.0.2", "127.0.0.2")

    async def test_connects_and_sends_tracking_to_entered_hostname(self):
        resolve = socket.getaddrinfo
        resolved_hosts = []

        def resolve_test_host(host, *args, **kwargs):
            if host == "stream-pc.example":
                resolved_hosts.append(host)
                host = "127.0.0.2"
            return resolve(host, *args, **kwargs)

        with (
            patch("socket.getaddrinfo", side_effect=resolve_test_host),
            patch.dict(os.environ, {"NO_PROXY": "*", "no_proxy": "*"}),
        ):
            await self.check_connection("stream-pc.example", "127.0.0.2")
        self.assertIn("stream-pc.example", resolved_hosts)

    async def test_hostname_connects_directly_despite_a_configured_proxy(self):
        with (
            patch("urllib.request.proxy_bypass", return_value=False),
            patch(
                "urllib.request.getproxies",
                return_value={"http": "http://127.0.0.1:1"},
            ),
        ):
            await self.check_connection("localhost", "127.0.0.1")

    async def test_name_resolution_failure_is_shown_in_the_window_status(self):
        settings.read_vts_endpoint("missing-pc.invalid", "8001")
        resolved = asyncio.Event()

        async def cannot_resolve(*args, **kwargs):
            resolved.set()
            raise socket.gaierror(socket.EAI_NONAME, "Unknown hostname")

        loop = asyncio.get_running_loop()
        with patch.object(loop, "getaddrinfo", side_effect=cannot_resolve):
            task = asyncio.create_task(vtube.session())
            try:
                await asyncio.wait_for(resolved.wait(), timeout=2)

                # Resolution runs within the client's connection task. Let its
                # error propagate to the session's visible status handler.
                async def wait_for_error():
                    while "Cannot resolve" not in state.status["detail"]:
                        await asyncio.sleep(0.01)

                await asyncio.wait_for(wait_for_error(), timeout=2)
                self.assertIn("missing-pc.invalid", state.status["detail"])
                self.assertIn("IP address", state.status["detail"])
                self.assertEqual(state.status["output"], "Waiting for VTube Studio")
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    async def test_connects_and_sends_tracking_to_entered_ipv6_address(self):
        # Some Windows and CI installations disable IPv6 loopback entirely.
        try:
            probe = await asyncio.start_server(lambda r, w: w.close(), "::1", 0)
        except OSError:
            self.skipTest("IPv6 loopback is unavailable")
        probe.close()
        await probe.wait_closed()
        await self.check_connection("::1", "::1")


if __name__ == "__main__":
    unittest.main()
