import types
import unittest
from unittest.mock import Mock, patch
from test_push import isolated_function


class ColdStartTests(unittest.TestCase):
    def test_web_server_starts_before_external_sync(self):
        order = []
        class Stop(BaseException):
            pass
        def stop(_bot):
            raise Stop()
        namespace = {
            "TELEGRAM_TOKEN": "test", "telebot": types.SimpleNamespace(TeleBot=Mock()),
            "coach": types.SimpleNamespace(reload=lambda **kwargs: order.append("sync")),
            "run_health_server": lambda bot: order.append("web"),
            "run_keep_alive_pinger": lambda: order.append("pinger"),
            "run_gym_reminder_scheduler": stop,
        }
        start = isolated_function("bot.py", "start_bot", namespace)
        with self.assertRaises(Stop):
            start()
        self.assertEqual(order, ["web", "pinger", "sync"])

    def test_keep_alive_targets_health_every_five_minutes(self):
        worker = []
        delays = []
        class Stop(BaseException):
            pass
        def sleep(delay):
            delays.append(delay)
            if delay == 300:
                raise Stop()
        def thread(**kwargs):
            worker.append(kwargs["target"])
            return types.SimpleNamespace(start=lambda: None)
        requests = types.ModuleType("requests")
        requests.get = Mock(return_value=types.SimpleNamespace(status_code=200))
        namespace = {"os": types.SimpleNamespace(getenv=lambda *args: "https://fit.test/"),
                     "time": types.SimpleNamespace(sleep=sleep), "threading": types.SimpleNamespace(Thread=thread)}
        start = isolated_function("bot.py", "run_keep_alive_pinger", namespace)
        with patch.dict("sys.modules", {"requests": requests}):
            start()
            with self.assertRaises(Stop):
                worker[0]()
        requests.get.assert_called_once_with("https://fit.test/health", timeout=20)
        self.assertEqual(delays, [30, 300])


if __name__ == "__main__":
    unittest.main()
