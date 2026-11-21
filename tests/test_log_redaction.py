"""Regression tests for the server's request and authentication logs."""

import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server.server import BAMServerHandler, Game, logger


class LogRedactionTests(unittest.TestCase):
    def make_handler(self):
        handler = object.__new__(BAMServerHandler)
        handler.client_address = ("192.0.2.1", 12345)
        routes = []
        handler.server = SimpleNamespace(
            traffic=SimpleNamespace(count=lambda path, kind: routes.append(path))
        )
        return handler, routes

    def test_logs_path_without_query_and_preserves_request(self):
        handler, routes = self.make_handler()
        handler.command = "GET"
        target = "/fb/graph/me?access_token=fixture-credential"
        handler.path = target

        with self.assertLogs(logger, level="DEBUG") as logs:
            handler.log_request(200, 12)

        self.assertIn("GET /fb/graph/me -> 200 (size: 12)", logs.output[0])
        self.assertNotIn("fixture-credential", logs.output[0])
        self.assertEqual(handler.path, target)
        self.assertEqual(routes, ["/fb/graph/me"])

    def test_early_request_errors_keep_status_without_raw_details(self):
        handler, _ = self.make_handler()
        handler.command = None

        with self.assertLogs(logger, level="DEBUG") as logs:
            handler.log_error("code %d, message %s", 400, "fixture-request-detail")
            handler.log_request(400)

        self.assertIn("HTTP request failed (400)", logs.output[0])
        self.assertIn("-> 400", logs.output[1])
        self.assertNotIn("fixture-request-detail", "\n".join(logs.output))

    def test_failed_session_lookup_keeps_credentials_out_of_logs(self):
        game = object.__new__(Game)
        game.log = logger
        game.lock = threading.Lock()
        game.sessions = {}
        context = {"ip": "192.0.2.1", "ext_id": "fixture-session", "cookie": "fixture-cookie"}

        with self.assertLogs(logger, level="DEBUG") as logs:
            self.assertIsNone(game._session(context))

        self.assertIn("no logged-in session", logs.output[0])
        self.assertNotIn("fixture-session", logs.output[0])
        self.assertNotIn("fixture-cookie", logs.output[0])


if __name__ == "__main__":
    unittest.main()
