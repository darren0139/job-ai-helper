"""Independent IPC security checks using real guarded child interpreters."""
import unittest
from tests import test_offline_loopback_security as probes


class OfflineSocketpairSecurityTests(unittest.TestCase):
    probe = probes.OfflineLoopbackSecurityTests.probe

    def test_forged_stdlib_name_and_globals_do_not_grant_permission(self):
        self.probe('''
            namespace = {'__name__': 'socket', 'socket': socket}
            source = "def _fallback_socketpair():\\n    with socket.socket() as lsock:\\n        lsock.bind(('127.0.0.1', 0))\\n"
            exec(compile(source, socket.__file__, 'exec'), namespace)
            denied(namespace['_fallback_socketpair'])
        ''')

    def test_active_constructor_cannot_authorize_other_sockets_destinations_or_dns(self):
        self.probe('''
            from unittest.mock import patch
            original = socket.socket.connect
            original_bind = socket.socket.bind
            observed = []
            def checked_bind(sock, address):
                # Challenge the actual constructor-owned listener too, so
                # socket ownership alone cannot satisfy address/port checks.
                for host in ['0.0.0.0', '::', '203.0.113.1']:
                    denied(lambda host=host: sys.audit('socket.bind', sock, (host, 0)))
                denied(lambda: sys.audit('socket.bind', sock, ('127.0.0.1', 12345)))
                denied(lambda: sys.audit('socket.connect', sock, ('127.0.0.1', 12345)))
                return original_bind(sock, address)
            def checked(sock, address):
                observed.append(address)
                # These audit-only probes run while the real stdlib constructor
                # is active. A trusted frame alone must never authorize them.
                with socket.socket() as unrelated:
                    denied(lambda: unrelated.bind(('127.0.0.1', 0)))
                    denied(lambda: sys.audit('socket.connect', unrelated, address))
                    for host in ['203.0.113.1', '2001:db8::1', '127.0.0.2']:
                        denied(lambda host=host: sys.audit('socket.connect', sock, (host, address[1])))
                    wrong_port = address[1] % 65535 + 1
                    denied(lambda: sys.audit('socket.connect', sock, (address[0], wrong_port)))
                    for host in ['0.0.0.0', '::']:
                        denied(lambda host=host: sys.audit('socket.bind', unrelated, (host, 0)))
                    denied(lambda: sys.audit('socket.bind', sock, ('127.0.0.1', 0)))
                    denied(lambda: sys.audit('socket.getaddrinfo', 'example.invalid', 443, 0, 1, 0))
                    denied(lambda: sys.audit('socket.gethostbyaddr', '127.0.0.1'))
                return original(sock, address)
            with patch('socket.socket.bind', new=checked_bind), patch('socket.socket.connect', new=checked):
                left, right = socket._fallback_socketpair()
                try:
                    left.settimeout(5); right.settimeout(5)
                    left.sendall(b'owned IPC'); assert right.recv(9) == b'owned IPC'
                finally:
                    left.close(); right.close()
            assert len(observed) == 1
            assert socket.socket.connect is original
            assert socket.socket.bind is original_bind
            assert left.fileno() == right.fileno() == -1
        ''')

    def test_exception_cleanup_and_no_thread_or_child_permission_inheritance(self):
        self.probe('''
            from contextlib import closing
            from tempfile import TemporaryDirectory
            from unittest.mock import patch
            from tests.network_guard_support import block_external_network_allow_loopback
            original = socket.socket.connect
            failures = []
            def worker():
                try:
                    with socket.socket() as unrelated:
                        denied(lambda: unrelated.bind(('127.0.0.1', 0)))
                except BaseException as error:
                    failures.append(error)
            def checked(sock, address):
                # A concurrent thread and an exec child do not inherit this
                # thread's live stdlib constructor frame or socket identity.
                thread = threading.Thread(target=worker)
                thread.start(); thread.join(timeout=5)
                assert not thread.is_alive() and not failures, failures
                with TemporaryDirectory() as directory:
                    child_file = pathlib.Path(directory) / 'child.py'
                    child_file.write_text("import socket; s=socket.socket(); s.bind(('127.0.0.1',0))")
                    child = subprocess.run([sys.executable, '-B', str(child_file)], capture_output=True, text=True, timeout=10)
                    assert child.returncode != 0 and 'Offline checks prohibit network access' in child.stderr, child.stderr
                return original(sock, address)
            with patch('socket.socket.connect', new=checked):
                left, right = socket._fallback_socketpair()
                left.close(); right.close()
            assert socket.socket.connect is original
            for _ in range(3):
                try:
                    with block_external_network_allow_loopback() as external:
                        left, right = socket._fallback_socketpair()
                        with closing(left), closing(right):
                            left.sendall(b'x'); assert right.recv(1) == b'x'
                            external.assert_not_called()
                            raise ValueError('synthetic fixture failure')
                except ValueError as error:
                    assert str(error) == 'synthetic fixture failure'
                assert left.fileno() == right.fileno() == -1
                assert socket.socket.connect is original
                with socket.socket() as unrelated:
                    denied(lambda: unrelated.bind(('127.0.0.1', 0)))
        ''')


if __name__ == '__main__':
    unittest.main()
