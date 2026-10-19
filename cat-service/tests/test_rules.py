import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rules import HIGH_TEMPERATURE, SUDDEN_INCREASE, AlarmRules


def make():
    return AlarmRules(jump_threshold=5, high_threshold=200)


class SuddenIncreaseTest(unittest.TestCase):
    def test_first_average_has_no_comparison(self):
        self.assertEqual(make().evaluate(100, None), [])

    def test_below_threshold(self):
        self.assertEqual(make().evaluate(104, 100), [])

    def test_exactly_at_threshold_triggers(self):
        self.assertEqual(make().evaluate(105, 100), [SUDDEN_INCREASE])

    def test_drop_also_triggers(self):
        self.assertEqual(make().evaluate(95, 100), [SUDDEN_INCREASE])

    def test_each_jump_is_reported(self):
        r = make()
        self.assertEqual(r.evaluate(110, 100), [SUDDEN_INCREASE])
        self.assertEqual(r.evaluate(120, 110), [SUDDEN_INCREASE])


class HighTemperatureTest(unittest.TestCase):
    def test_exactly_at_limit_does_not_trigger(self):
        self.assertEqual(make().evaluate(200, 200), [])

    def test_triggers_above_limit(self):
        self.assertEqual(make().evaluate(201, 200), [HIGH_TEMPERATURE])

    def test_first_average_can_be_high(self):
        self.assertEqual(make().evaluate(250, None), [HIGH_TEMPERATURE])

    def test_not_repeated_while_high(self):
        r = make()
        self.assertEqual(r.evaluate(210, 201), [SUDDEN_INCREASE, HIGH_TEMPERATURE])
        self.assertEqual(r.evaluate(211, 210), [])
        self.assertEqual(r.evaluate(212, 211), [])

    def test_rearms_after_dropping(self):
        r = make()
        r.evaluate(210, None)
        self.assertEqual(r.evaluate(199, 210), [SUDDEN_INCREASE])
        self.assertEqual(r.evaluate(205, 199), [SUDDEN_INCREASE, HIGH_TEMPERATURE])


if __name__ == "__main__":
    unittest.main()
