"""Real Windows asyncio/Streamlit IPC plus fail-closed external destinations."""
import asyncio
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import Mock, patch

from tests.network_guard_support import block_external_network_allow_loopback
from scripts.offline_loopback import loopback_http_scope


class NetworkGuardTests(unittest.TestCase):
    def allowed(self, address, family=socket.AF_INET):
        sock = Mock(family=family)
        with patch('socket.socket.connect', return_value='local IPC') as original:
            with block_external_network_allow_loopback() as external:
                self.assertEqual(socket.socket.connect(sock, address), 'local IPC')
                original.assert_called_once_with(sock, address)
                external.assert_not_called()

    def blocked(self, address):
        with patch('socket.getaddrinfo', side_effect=AssertionError('No DNS')) as dns:
            with block_external_network_allow_loopback() as external:
                with self.assertRaisesRegex(AssertionError, 'external network'):
                    socket.socket.connect(Mock(family=socket.AF_INET), address)
                external.assert_called_once_with(address)
            dns.assert_not_called()

    def test_ipv4_loopback_allowed(self):
        self.allowed(('127.0.0.1', 80))

    def test_entire_ipv4_loopback_range_allowed(self):
        self.allowed(('127.12.34.56', 80))

    def test_ipv6_loopback_allowed(self):
        self.allowed(('::1', 80, 0, 0), socket.AF_INET6)

    def test_localhost_allowed(self):
        self.allowed(('localhost', 80))

    def test_external_ip_blocked_and_recorded(self):
        self.blocked(('203.0.113.1', 443))

    def test_external_hostname_blocked_without_dns(self):
        self.blocked(('api.example.test', 443))

    def test_private_lan_addresses_blocked(self):
        for host in ('10.0.0.1', '172.16.0.1', '192.168.1.1', '169.254.1.1'):
            with self.subTest(host=host):
                self.blocked((host, 443))

    def test_hostname_lookalike_and_malformed_address_fail_closed(self):
        for address in (('localhost.example.test', 443), ('127.0.0.1.example.test', 443), None, '', (), (b'localhost', 80)):
            with self.subTest(address=address):
                self.blocked(address)

    def test_local_unix_ipc_delegates_if_supported(self):
        if not hasattr(socket, 'AF_UNIX'):
            self.skipTest('AF_UNIX unavailable')
        self.allowed('local-ipc-path', socket.AF_UNIX)

    def test_real_ipv4_connect_is_allowed_without_external_attempt(self):
        with loopback_http_scope(), socket.socket() as server:
            server.bind(('127.0.0.1', 0)); server.listen(1)
            with block_external_network_allow_loopback() as external, socket.socket() as client:
                client.settimeout(5); client.connect(server.getsockname())
                peer, _ = server.accept(); peer.close()
                external.assert_not_called()
        self.assertEqual(server.fileno(), -1);self.assertEqual(client.fileno(), -1)

    def test_real_ipv6_connect_if_supported(self):
        try:
            with block_external_network_allow_loopback() as external:
                left, right = socket._fallback_socketpair(socket.AF_INET6, socket.SOCK_STREAM, 0)
        except OSError as exc:
            self.skipTest('IPv6 loopback unavailable: ' + str(exc))
        try:
            self.assertEqual(left.family, socket.AF_INET6)
            self.assertEqual(right.family, socket.AF_INET6)
            self.assertEqual(left.getsockname()[0], '::1')
            self.assertGreater(left.getsockname()[1], 0)
            left.settimeout(5); right.settimeout(5)
            left.sendall(b'IPv6 IPC'); self.assertEqual(right.recv(8), b'IPv6 IPC')
            external.assert_not_called()
        finally:
            left.close(); right.close()
        self.assertEqual(left.fileno(), -1);self.assertEqual(right.fileno(), -1)

    def test_asyncio_native_event_loop_runs_and_closes(self):
        with block_external_network_allow_loopback() as external:
            loop = asyncio.new_event_loop()
            try:
                # Windows selects ProactorEventLoop through the normal policy.
                if hasattr(asyncio, 'ProactorEventLoop'):
                    self.assertIsInstance(loop, asyncio.ProactorEventLoop)
                self.assertEqual(loop.run_until_complete(asyncio.sleep(0, result='done')), 'done')
            finally:
                loop.close()
            self.assertTrue(loop.is_closed())
            external.assert_not_called()

    def test_fallback_socketpair_connect_is_allowed(self):
        with block_external_network_allow_loopback() as external:
            left, right = socket._fallback_socketpair(socket.AF_INET, socket.SOCK_STREAM, 0)
            try:
                left.send(b'x'); self.assertEqual(right.recv(1), b'x')
            finally:
                left.close(); right.close()
            external.assert_not_called()

    def test_streamlit_from_string_under_guard(self):
        from streamlit.testing.v1 import AppTest
        with block_external_network_allow_loopback() as external:
            app = AppTest.from_string("import streamlit as st\nst.write('local smoke')").run(timeout=30)
            self.assertFalse(app.exception)
            self.assertEqual(app.markdown[0].value, 'local smoke')
            external.assert_not_called()

    def test_streamlit_from_file_under_guard(self):
        from streamlit.testing.v1 import AppTest
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'harness.py'
            path.write_text("import streamlit as st\nst.write('local file smoke')", encoding='utf-8')
            with block_external_network_allow_loopback() as external:
                app = AppTest.from_file(str(path)).run(timeout=30)
                self.assertFalse(app.exception)
                self.assertEqual(app.markdown[0].value, 'local file smoke')
                external.assert_not_called()

    def test_connect_restored_after_normal_exit(self):
        original = socket.socket.connect
        with block_external_network_allow_loopback():
            self.assertIsNot(socket.socket.connect, original)
        self.assertIs(socket.socket.connect, original)

    def test_connect_restored_after_exception(self):
        original = socket.socket.connect
        with self.assertRaisesRegex(ValueError, 'fixture'):
            with block_external_network_allow_loopback():
                raise ValueError('fixture')
        self.assertIs(socket.socket.connect, original)

    def test_repeated_use_leaks_no_patch(self):
        original = socket.socket.connect
        for _ in range(3):
            with block_external_network_allow_loopback() as external:
                external.assert_not_called()
            self.assertIs(socket.socket.connect, original)

    def test_nested_use_restores_outer_wrapper_then_original(self):
        original = socket.socket.connect
        with block_external_network_allow_loopback() as outer:
            with block_external_network_allow_loopback() as inner:
                self.assertIs(socket.socket.connect, inner.connect_wrapper)
                with self.assertRaises(AssertionError):
                    socket.socket.connect(Mock(family=socket.AF_INET), ('remote.test', 443))
                inner.assert_called_once()
                outer.assert_not_called()
            self.assertIs(socket.socket.connect, outer.connect_wrapper)
        self.assertIs(socket.socket.connect, original)
