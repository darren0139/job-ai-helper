"""No live socket use: verify audit isolation and transport restoration."""
from contextvars import copy_context
import os
import socket
import unittest
from unittest.mock import Mock, patch

from taxonomy_discovery.offline_execution import offline_execution, research_execution, network_blocker


class OfflineExecutionTests(unittest.TestCase):
    def test_overlapping_audits_exit_out_of_order_without_leaking(self):
        base = Mock(return_value="fake transport")
        with patch.object(socket.socket, "connect", base), patch.dict(os.environ, {"CAPABILITY_RAG_MODE": "shadow"}):
            first, second = copy_context(), copy_context()
            a, b = offline_execution("Offline corpus forbids network"), offline_execution("Second offline audit")
            first.run(a.__enter__)
            second.run(b.__enter__)
            for ctx, reason in ((first, "Offline corpus"), (second, "Second offline")):
                with self.assertRaisesRegex(RuntimeError, reason):
                    ctx.run(socket.socket.connect, None, ("fake", 0))
            first.run(a.__exit__, None, None, None)
            self.assertEqual(os.environ["CAPABILITY_RAG_MODE"], "off")
            with self.assertRaisesRegex(RuntimeError, "Second offline"):
                second.run(socket.socket.connect, None, ("fake", 0))
            # Explicit research/other contexts use the original fake transport.
            with research_execution():
                self.assertEqual(socket.socket.connect(None, ("fake", 0)), "fake transport")
            second.run(b.__exit__, None, None, None)
            self.assertIs(socket.socket.connect, base)
            self.assertEqual(os.environ["CAPABILITY_RAG_MODE"], "shadow")

    def test_nested_audit_policy_restored_after_research_and_exceptions(self):
        base = Mock(return_value="fake")
        with patch.object(socket.socket, "connect", base):
            with self.assertRaisesRegex(ValueError, "test"):
                with offline_execution("Audit offline"):
                    with research_execution():
                        self.assertEqual(socket.socket.connect(None, None), "fake")
                    with self.assertRaisesRegex(RuntimeError, "Audit offline"):
                        socket.socket.connect(None, None)
                    raise ValueError("test")
            self.assertIs(socket.socket.connect, base)

    def test_independent_restriction_is_never_bypassed(self):
        with patch.object(socket.socket, "connect", side_effect=RuntimeError("Independent network restriction")) as base:
            with offline_execution("Audit offline"), research_execution():
                with self.assertRaisesRegex(RuntimeError, "Independent"):
                    socket.socket.connect(None, None)
            self.assertIs(socket.socket.connect, base)

    def test_abandoned_legacy_guard_is_reported_not_removed(self):
        with patch.object(socket.socket, "connect", side_effect=RuntimeError("Offline corpus forbids network")) as base:
            self.assertIn("restart Streamlit", network_blocker())
            self.assertIs(socket.socket.connect, base)
