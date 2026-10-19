import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from window import ReadingBuffer, compute_average


class ComputeAverageTest(unittest.TestCase):
    def test_empty_returns_none(self):
        self.assertIsNone(compute_average([]))

    def test_single_sensor(self):
        avg, n = compute_average([(0, "a", 10), (1, "a", 20)])
        self.assertEqual((avg, n), (15, 1))

    def test_mean_of_sensor_means(self):
        # a: média 10 (3 leituras), b: média 40 (1 leitura) -> 25, não 17.5
        readings = [(0, "a", 10), (1, "a", 10), (2, "a", 10), (3, "b", 40)]
        avg, n = compute_average(readings)
        self.assertEqual((avg, n), (25, 2))


class ReadingBufferTest(unittest.TestCase):
    def test_discards_old_readings(self):
        buf = ReadingBuffer(120)
        buf.add(0, "a", 1)
        buf.add(50, "a", 2)
        buf.add(100, "a", 3)
        snap = buf.snapshot(130)  # corte em 10: sai a leitura de ts=0
        self.assertEqual([r[0] for r in snap], [50, 100])

    def test_reading_exactly_at_window_edge_is_kept(self):
        buf = ReadingBuffer(120)
        buf.add(10, "a", 1)
        self.assertEqual(len(buf.snapshot(130)), 1)
        self.assertEqual(len(buf.snapshot(131)), 0)

    def test_snapshot_is_a_copy(self):
        buf = ReadingBuffer(120)
        buf.add(0, "a", 1)
        snap = buf.snapshot(0)
        buf.add(1, "a", 2)
        self.assertEqual(len(snap), 1)

    def test_concurrent_adds(self):
        buf = ReadingBuffer(1000)

        def worker(i):
            for j in range(500):
                buf.add(j, f"s{i}", 1.0)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(buf.snapshot(500)), 8 * 500)


if __name__ == "__main__":
    unittest.main()
