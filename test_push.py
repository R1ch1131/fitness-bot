"""Offline regressions: real crypto/serialization, mocked transport and storage."""
import ast
import base64
import copy
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from py_vapid import Vapid
from pywebpush import WebPushException
import push_service as push

ROOT = Path(__file__).parent


def isolated_function(filename, name, namespace):
    """Load scheduler/API functions without starting Telegram, AI, or API clients."""
    tree = ast.parse((ROOT / filename).read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    exec(compile(ast.Module(body=[node], type_ignores=[]), filename, "exec"), namespace)
    return namespace[name]


class PushTests(unittest.TestCase):
    def setUp(self):
        public = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        enc = lambda value: base64.urlsafe_b64encode(value).decode().rstrip("=")
        self.sub = {"endpoint": "https://web.push.apple.com/device-token", "keys": {
            "p256dh": enc(public), "auth": enc(b"0123456789abcdef")}}

    def test_validate_provider_and_keys(self):
        self.assertTrue(push.validate_subscription(self.sub))
        for url in ["http://web.push.apple.com/a", "https://web.push.apple.com.evil.test/a", "https://127.0.0.1/a", "https://user@web.push.apple.com/a"]:
            self.assertFalse(push.validate_subscription(dict(self.sub, endpoint=url)))
        self.assertFalse(push.validate_subscription({"endpoint": self.sub["endpoint"], "keys": {"p256dh": "bad", "auth": "bad"}}))

    def test_empty_cloud_list_does_not_resurrect_local_subscriptions(self):
        with patch("cloud_storage.is_cloud_configured", return_value=True), patch("cloud_storage.get_cloud_data", return_value=[]):
            self.assertEqual(push.load_subscriptions(), [])

    def test_cloud_failure_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory(dir=push.DATA_DIR) as tmp, patch.object(push, "SUBSCRIPTIONS_FILE", str(Path(tmp) / "subs.json")), patch("cloud_storage.is_cloud_configured", return_value=True), patch("cloud_storage.set_cloud_data", return_value=False):
            with self.assertRaises(RuntimeError):
                push.save_subscriptions([self.sub])

    def test_keys_survive_restart_and_environment_override(self):
        with tempfile.TemporaryDirectory(dir=push.DATA_DIR) as tmp, patch.object(push, "VAPID_FILE", str(Path(tmp) / "keys.json")), patch("cloud_storage.is_cloud_configured", return_value=False), patch.dict("os.environ", {"VAPID_PRIVATE_KEY_PEM": ""}):
            push._cached_vapid_keys = None
            first = push.get_or_create_vapid_keys()
            push._cached_vapid_keys = None
            self.assertEqual(push.get_or_create_vapid_keys(), first)
            v = Vapid()
            v.generate_keys()
            with patch.dict("os.environ", {"VAPID_PRIVATE_KEY_PEM": v.private_pem().decode().replace("\n", "\\n")}):
                push._cached_vapid_keys = None
                changed = push.get_or_create_vapid_keys()
                self.assertNotEqual(changed["public_b64"], first["public_b64"])
                self.assertEqual(len(base64.urlsafe_b64decode(changed["public_b64"] + "=")), 65)
        push._cached_vapid_keys = None

    def test_targeted_delivery_and_expired_cleanup(self):
        v = Vapid()
        v.generate_keys()
        other = dict(self.sub, endpoint="https://web.push.apple.com/other")
        with patch.object(push, "load_subscriptions", return_value=[self.sub, other]), patch.object(push, "get_or_create_vapid_keys", return_value={"private_pem": v.private_pem().decode()}), patch.object(push, "webpush") as transport, patch.object(push, "remove_subscription") as remove:
            self.assertEqual(push.send_push_notification("Test", "Body", endpoint=self.sub["endpoint"], tag="test"), 1)
            self.assertEqual(transport.call_count, 1)
            self.assertEqual(json.loads(transport.call_args.kwargs["data"])["tag"], "test")
            self.assertEqual(transport.call_args.kwargs["timeout"], 10)
            transport.side_effect = WebPushException("Gone", response=types.SimpleNamespace(status_code=410))
            self.assertEqual(push.send_push_notification("Test", "Body", endpoint=self.sub["endpoint"]), 0)
            remove.assert_called_once_with(self.sub["endpoint"])


class DispatcherTests(unittest.TestCase):
    def dispatch(self, pending, telegram_subs=None, push_result=1, telegram_failure=False):
        self.pending = copy.deepcopy(pending)
        self.send = Mock(return_value=push_result)
        self.bot = Mock()
        if telegram_failure:
            self.bot.send_message.side_effect = RuntimeError("Telegram unavailable")
        namespace = {"Optional": __import__("typing").Optional, "time": types.SimpleNamespace(time=lambda: 2000),
                     "load_pending_checkin": lambda: self.pending, "save_pending_checkin": lambda p: None,
                     "get_all_subscribers": lambda: telegram_subs or [], "coach": types.SimpleNamespace(workouts=[])}
        fn = isolated_function("bot.py", "dispatch_checkin_if_due", namespace)
        with patch.object(push, "send_push_notification", self.send):
            fn(self.bot)

    def test_push_without_telegram_and_no_duplicate(self):
        self.dispatch({"due_time": 1900, "workout_id": "1"})
        self.send.assert_called_once()
        self.assertTrue(self.pending["push_sent"])
        self.dispatch(self.pending)
        self.send.assert_not_called()

    def test_telegram_success_does_not_block_push_retry(self):
        self.dispatch({"due_time": 1900, "prompt_sent": True}, push_result=0)
        self.send.assert_called_once()
        self.assertFalse(self.pending.get("push_sent", False))

    def test_future_responded_and_expired_are_not_sent(self):
        for pending in [{"due_time": 3000}, {"due_time": 1900, "responded": True}, {"due_time": -30000}]:
            self.dispatch(pending)
            self.send.assert_not_called()

    def test_telegram_failure_does_not_block_push(self):
        self.dispatch({"due_time": 1900}, telegram_subs=[123], telegram_failure=True)
        self.send.assert_called_once()
        self.bot.send_message.assert_called_once()


if __name__ == "__main__":
    unittest.main()
