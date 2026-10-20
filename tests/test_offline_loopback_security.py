"""Independent, contained child-process probes; never contact external services."""
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import textwrap
import unittest


PRELUDE = '''
import contextvars, os, pathlib, socket, sqlite3, subprocess, sys, threading
from scripts.offline_loopback import loopback_http_scope
def denied(callback, prefix='Offline checks prohibit'):
    try:
        callback()
    except RuntimeError as error:
        assert str(error).startswith(prefix), str(error)
    else:
        raise AssertionError('Unauthorized operation was accepted')
'''


class OfflineLoopbackSecurityTests(unittest.TestCase):
    def probe(self, source):
        # Also runs under ordinary unittest/hosted CI: each probe installs the
        # actual release guard in a fresh interpreter, not a mock predicate.
        with TemporaryDirectory() as temporary:
            root = Path(__file__).resolve().parents[1]
            scratch = Path(temporary)
            env = dict(os.environ)
            if not env.get("JOB_MATCH_TEST_GUARD_DIR"):
                guard = scratch / "guard"
                guard.mkdir()
                (guard / "sitecustomize.py").write_text(
                    "from scripts.offline_release_guard import install\ninstall()\n",
                    encoding="utf-8",
                )
                env.update(
                    JOB_MATCH_TEST_ROOT=str(root), JOB_MATCH_TEST_SCRATCH=str(scratch),
                    JOB_MATCH_TEST_GUARD_DIR=str(guard),
                    PYTHONPATH=os.pathsep.join((str(guard), str(root))),
                    PYTHONDONTWRITEBYTECODE="1", PYTHON_DOTENV_DISABLED="true",
                )
            probe_file = scratch / "probe.py"
            probe_file.write_text(PRELUDE + textwrap.dedent(source), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-B", str(probe_file)],
                env=env, cwd=root, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_default_scope_and_inherited_environment_grant_nothing(self):
        self.probe('''
            os.environ['ALLOW_LOOPBACK'] = '1'
            with socket.socket() as sock:
                denied(lambda: sock.bind(('127.0.0.1', 0)))
                denied(lambda: sock.connect(('127.0.0.1', 9)))
            denied(lambda: socket.create_connection(('127.0.0.1', 9)))
        ''')

    def test_scope_denies_other_addresses_ports_dns_udp_and_second_listener(self):
        self.probe('''
            # Audit-only external controls cannot send traffic even on failure.
            with loopback_http_scope(), socket.socket() as listener:
                for address in [('0.0.0.0', 0), ('127.0.0.2', 0), ('203.0.113.1', 0)]:
                    denied(lambda address=address: sys.audit('socket.bind', listener, address))
                listener.bind(('127.0.0.1', 0))
                port = listener.getsockname()[1]
                with socket.socket() as other:
                    denied(lambda: other.bind(('127.0.0.1', 0)))
                    for address in [('203.0.113.1', 443), ('127.0.0.1', port % 65535 + 1), ('::1', port), ('2001:db8::1', 443)]:
                        denied(lambda address=address: sys.audit('socket.connect', other, address))
                    for host in ['localhost', 'example.invalid', '::1', '2001:db8::1']:
                        denied(lambda host=host: sys.audit('socket.getaddrinfo', host, port, 0, 1, 0))
                    denied(lambda: sys.audit('socket.bind', other, ('::', 0, 0, 0)))
                    denied(lambda: sys.audit('socket.sendto', other, ('127.0.0.1', port)))
                    denied(lambda: sys.audit('socket.sendmsg', other, ('127.0.0.1', port)))
                for event in ['socket.gethostbyname', 'socket.gethostbyaddr', 'socket.getnameinfo']:
                    denied(lambda event=event: sys.audit(event, 'example.invalid'))
                with socket.socket(type=socket.SOCK_DGRAM) as udp:
                    denied(lambda: sys.audit('socket.connect', udp, ('127.0.0.1', port)))
                if socket.has_ipv6:
                    with socket.socket(socket.AF_INET6) as ipv6:
                        denied(lambda: sys.audit('socket.bind', ipv6, ('::1', 0, 0, 0)))
        ''')

    def test_exception_exit_threads_and_python_children_do_not_inherit_permission(self):
        self.probe('''
            try:
                with loopback_http_scope(), socket.socket() as listener:
                    listener.bind(('127.0.0.1', 0))
                    errors = []
                    def worker():
                        try:
                            with socket.socket() as sock:
                                denied(lambda: sock.bind(('127.0.0.1', 0)))
                        except BaseException as error:
                            errors.append(error)
                    copied = contextvars.copy_context()
                    thread = threading.Thread(target=lambda: copied.run(worker))
                    thread.start(); thread.join(timeout=5)
                    assert not thread.is_alive() and not errors, errors
                    code = "import socket; s=socket.socket(); s.bind(('127.0.0.1',0))"
                    child = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True, timeout=10)
                    assert child.returncode != 0 and 'Offline checks prohibit network access' in child.stderr, child.stderr
                    raise ValueError('synthetic scope exception')
            except ValueError:
                pass
            assert listener.fileno() == -1
            with socket.socket() as sock:
                denied(lambda: sock.bind(('127.0.0.1', 0)))
            # A later scope is independent and still supports only port zero.
            with loopback_http_scope(), socket.socket() as later:
                later.bind(('127.0.0.1', 0))
                assert later.getsockname()[1] > 0
        ''')

    def test_network_scope_preserves_filesystem_database_and_child_guards(self):
        self.probe('''
            with loopback_http_scope():
                target = pathlib.Path(os.environ['JOB_MATCH_TEST_ROOT']) / 'unauthorized-loopback-probe.txt'
                denied(lambda: target.write_text('must not be created'))
                assert not target.exists()
                denied(lambda: sqlite3.connect(str(target.with_suffix('.sqlite3'))))
                denied(lambda: subprocess.run([sys.executable, '-S', '-c', 'pass']),
                       'Offline Python children must inherit containment')
        ''')


if __name__ == "__main__":
    unittest.main()
