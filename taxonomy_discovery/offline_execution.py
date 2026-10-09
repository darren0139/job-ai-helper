"""Context-local audit network policy with overlap-safe socket restoration.

Unlike overlapping mock.patch scopes, the last exiting audit restores the
original transport regardless of exit order. Other contexts still use that
original transport, including any independently installed network restriction.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import os
import socket
from threading import RLock

_reason = ContextVar("taxonomy_offline_reason", default=None)
_lock = RLock()
_users = 0
_connect = None
_rag_mode = None


def _guarded_connect(sock, *args, **kwargs):
    reason = _reason.get()
    if reason:
        raise RuntimeError(reason)
    return _connect(sock, *args, **kwargs)


@contextmanager
def offline_execution(reason):
    global _users, _connect, _rag_mode
    with _lock:
        if not _users:
            _connect = socket.socket.connect
            _rag_mode = os.environ.get("CAPABILITY_RAG_MODE")
            socket.socket.connect = _guarded_connect
            os.environ["CAPABILITY_RAG_MODE"] = "off"
        _users += 1
    token = _reason.set(reason)
    try:
        yield
    finally:
        _reason.reset(token)
        with _lock:
            _users -= 1
            if not _users:
                # Do not overwrite an independently installed restriction.
                if socket.socket.connect is _guarded_connect:
                    socket.socket.connect = _connect
                if _rag_mode is None:
                    os.environ.pop("CAPABILITY_RAG_MODE", None)
                else:
                    os.environ["CAPABILITY_RAG_MODE"] = _rag_mode


@contextmanager
def research_execution():
    """New explicit research phase; never bypass independent provider controls."""
    token = _reason.set(None)
    try:
        yield
    finally:
        _reason.reset(token)


def network_blocker():
    """Recognize an abandoned legacy audit mock without removing restrictions."""
    transport = _connect if socket.socket.connect is _guarded_connect else socket.socket.connect
    error = getattr(transport, "side_effect", None)
    legacy_reasons = {"Offline corpus forbids network", "Maintenance audit is offline",
                      "Offline validation", "Offline taxonomy review",
                      "Offline preview forbids network", "Offline publication refresh forbids network",
                      "Deterministic backfill forbids network", "Snapshot scoring forbids network"}
    if isinstance(error, RuntimeError) and str(error) in legacy_reasons:
        return "Legacy offline guard still installed; restart Streamlit before explicit research"
    return None
