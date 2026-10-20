"""Explicit socket capability for one test-owned HTTP listener, never an env flag.

This module grants no permission on import. Both offline audit hooks consult it.
It is test infrastructure, not an application networking configuration.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import os
import socket
import threading
import weakref


_scope = ContextVar("offline_loopback_http_scope", default=None)


@contextmanager
def loopback_http_scope():
    """Allow one ephemeral IPv4 TCP listener and clients to its exact port.

    No permission survives exit, copied thread contexts, fork or Python exec.
    The fixture must stop its server before leaving; close the listener as a
    final safeguard on exceptional fixture setup. No DNS is needed or allowed.
    """
    if _scope.get() is not None:
        raise RuntimeError("Nested loopback test scopes are prohibited")
    state = {"pid": os.getpid(), "thread": threading.get_ident(),
             "active": True, "listener": None}
    token = _scope.set(state)
    try:
        yield
    finally:
        state["active"] = False
        _scope.reset(token)
        listener = state["listener"]() if state["listener"] else None
        if listener is not None:
            listener.close()


def loopback_socket_allowed(event, args):
    """Validate audited numeric addresses before an OS networking operation."""
    state = _scope.get()
    if (state is None or not state["active"] or state["pid"] != os.getpid()
            or state["thread"] != threading.get_ident()):
        return False
    if event == "socket.bind":
        sock, address = args
        if (state["listener"] is None and sock.family == socket.AF_INET
                and sock.type == socket.SOCK_STREAM
                and address == ("127.0.0.1", 0)):
            state["listener"] = weakref.ref(sock)
            return True
        return False
    listener = state["listener"]() if state["listener"] else None
    if listener is None or listener.fileno() < 0:
        return False
    address = listener.getsockname()
    if address[0] != "127.0.0.1" or address[1] <= 0:
        return False
    if event == "socket.connect":
        sock, destination = args
        return (sock.family == socket.AF_INET and sock.type == socket.SOCK_STREAM
                and destination == address)
    if event == "socket.getaddrinfo":
        host, port, family, socktype, protocol = args
        return (host == address[0] and port == address[1]
                and family in (socket.AF_UNSPEC, socket.AF_INET)
                and socktype == socket.SOCK_STREAM
                and protocol in (0, socket.IPPROTO_TCP))
    return False
