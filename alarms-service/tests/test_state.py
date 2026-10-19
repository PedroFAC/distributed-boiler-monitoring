import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from state import AlarmsState

P = "plant/boiler1"


def msg(state, topic, payload, now=1000):
    if not isinstance(payload, bytes):
        payload = json.dumps(payload).encode()
    state.handle_message(topic, payload, now)


class AlarmsStateTest(unittest.TestCase):
    def setUp(self):
        self.state = AlarmsState(high_threshold=200, max_alarms=3, max_history=3)
        self.changes = []
        self.state.subscribe(self.changes.append)

    def test_high_temperature_alarm(self):
        msg(self.state, f"{P}/events/high_temperature",
            {"type": "high_temperature", "avg": 213.5, "prev_avg": 198.0, "ts": 10})
        alarm = self.state.snapshot()["alarms"][0]
        self.assertEqual(alarm["label"], "TEMPERATURA ALTA")
        self.assertEqual(alarm["severity"], "high")
        self.assertEqual(self.changes[-1]["kind"], "alarm")

    def test_sudden_increase_is_warning(self):
        msg(self.state, f"{P}/events/sudden_increase",
            {"type": "sudden_increase", "avg": 90, "prev_avg": 80, "ts": 10})
        self.assertEqual(self.state.snapshot()["alarms"][0]["severity"], "warning")

    def test_unknown_event_ignored(self):
        msg(self.state, f"{P}/events/other", {"avg": 1, "ts": 1})
        self.assertEqual(self.state.snapshot()["alarms"], [])

    def test_alarms_newest_first_and_capped(self):
        for i in range(5):
            msg(self.state, f"{P}/events/sudden_increase",
                {"avg": 80 + i, "prev_avg": 70, "ts": i})
        alarms = self.state.snapshot()["alarms"]
        self.assertEqual([a["ts"] for a in alarms], [4, 3, 2])

    def test_average_updates_history_and_last(self):
        for i in range(4):
            msg(self.state, f"{P}/cat/average",
                {"avg": 80 + i, "prev_avg": None, "sensors": 3, "window_s": 10, "ts": i})
        snap = self.state.snapshot()
        self.assertEqual([p["ts"] for p in snap["history"]], [1, 2, 3])
        self.assertEqual(snap["last_average"]["avg"], 83)

    def test_invalid_payloads_ignored(self):
        msg(self.state, f"{P}/cat/average", b"not json")
        msg(self.state, f"{P}/events/high_temperature", {"ts": 1})
        snap = self.state.snapshot()
        self.assertEqual((snap["history"], snap["alarms"]), ([], []))

    def test_sensor_status(self):
        msg(self.state, f"{P}/sensors/sim-b/status", b"online", now=5)
        msg(self.state, f"{P}/sensors/sim-a/status", b"online", now=6)
        msg(self.state, f"{P}/sensors/sim-b/status", b"offline", now=7)
        msg(self.state, f"{P}/sensors/sim-c/status", b"garbage")
        sensors = self.state.snapshot()["sensors"]
        self.assertEqual(
            [(s["id"], s["status"]) for s in sensors],
            [("sim-a", "online"), ("sim-b", "offline")],
        )

    def test_clear_alarms(self):
        msg(self.state, f"{P}/events/high_temperature", {"avg": 210, "ts": 1})
        self.state.clear_alarms()
        self.assertEqual(self.state.snapshot()["alarms"], [])
        self.assertEqual(self.changes[-1]["kind"], "clear")

    def test_broker_connection_emits_only_on_change(self):
        self.state.set_broker_connected(True)
        self.state.set_broker_connected(True)
        self.assertEqual([c["kind"] for c in self.changes], ["connection"])

    def test_foreign_topic_ignored(self):
        msg(self.state, "other/boiler1/events/high_temperature", {"avg": 210, "ts": 1})
        self.assertEqual(self.state.snapshot()["alarms"], [])


if __name__ == "__main__":
    unittest.main()
