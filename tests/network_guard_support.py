"""Reject external socket attempts while permitting local event-loop IPC.

No DNS resolution is performed to decide whether a destination is loopback.
Capture the active connect at entry so nested guards/offline scopes restore
their caller's patch rather than bypassing it.
"""
from contextlib import contextmanager
import ipaddress
import socket
from unittest.mock import Mock, patch


def _is_loopback(address):
    if not isinstance(address, tuple) or not address:
        return False
    host = address[0]
    if not isinstance(host, str):
        return False
    if host.casefold() == 'localhost':
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@contextmanager
def block_external_network_allow_loopback():
    """Yield the external-attempt Mock (allowed loopback never calls it)."""
    original_connect = socket.socket.connect
    external_attempt = Mock(side_effect=AssertionError('Runtime external network call'))

    def connect(sock, address):
        family = getattr(sock, 'family', None)
        if (family in (socket.AF_INET, socket.AF_INET6) and _is_loopback(address)) or (
                hasattr(socket, 'AF_UNIX') and family == socket.AF_UNIX):
            return original_connect(sock, address)
        return external_attempt(address)

    # Existing fixture assertions continue to track only external attempts;
    # restoration tests can inspect the separately installed wrapper.
    external_attempt.connect_wrapper = connect
    with patch('socket.socket.connect', new=connect):
        yield external_attempt
