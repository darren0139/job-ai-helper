"""Recognize only socket operations owned by the real stdlib IPC constructor.

No persistent permission, hostname lookup, test name or filename allowlist.
Capture the stdlib code identity before test fixtures install wrappers.
"""
import socket
import sys


_SOCKETPAIR_CODE = socket._fallback_socketpair.__code__


def stdlib_socketpair_allowed(event, args):
    """Verify the constructor's own ephemeral listener and exact client peer.

    Transparent connect wrappers may intervene. A trusted code frame alone is
    insufficient: the audited socket must be that frame's own socket. IPv6 is
    private to stdlib IPC here, never added to the browser HTTP scope.
    """
    if event not in ("socket.bind", "socket.connect"):
        return False
    sock, address = args
    frame = sys._getframe(1)
    try:
        while frame is not None:
            if frame.f_code is _SOCKETPAIR_CODE:
                listener = frame.f_locals.get("lsock")
                if listener is None or listener.type != socket.SOCK_STREAM:
                    return False
                host = {socket.AF_INET: "127.0.0.1", socket.AF_INET6: "::1"}.get(listener.family)
                if host is None:
                    return False
                if event == "socket.bind":
                    return sock is listener and address == (host, 0)
                client = frame.f_locals.get("csock")
                if (client is None or sock is not client or client.family != listener.family
                        or client.type != socket.SOCK_STREAM or listener.fileno() < 0):
                    return False
                peer = listener.getsockname()[:2]
                return peer[0] == host and peer[1] > 0 and address == peer
            frame = frame.f_back
        return False
    finally:
        del frame
