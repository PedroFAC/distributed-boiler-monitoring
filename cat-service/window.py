"""Janela deslizante de leituras e cálculo da média. Sem I/O."""

import threading
from collections import defaultdict


class ReadingBuffer:
    """Buffer de leituras (ts, sensor_id, value) compartilhado entre threads.

    O callback do MQTT chama add() e o timer chama snapshot(); o Lock protege
    a lista contra acesso concorrente.
    """

    def __init__(self, window_s):
        self._window_s = window_s
        self._lock = threading.Lock()
        self._readings = []

    def add(self, ts, sensor_id, value):
        with self._lock:
            self._readings.append((ts, sensor_id, value))

    def snapshot(self, now):
        """Descarta leituras com mais de window_s e devolve uma cópia do resto."""
        cutoff = now - self._window_s
        with self._lock:
            self._readings = [r for r in self._readings if r[0] >= cutoff]
            return list(self._readings)


def compute_average(readings):
    """Média das médias por sensor.

    Cada sensor pesa igual, mesmo que tenha mais leituras na janela (por
    exemplo, um sensor com intervalo menor). Devolve (avg, n_sensores) ou
    None se não houver leituras.
    """
    by_sensor = defaultdict(list)
    for _, sensor_id, value in readings:
        by_sensor[sensor_id].append(value)
    if not by_sensor:
        return None
    means = [sum(v) / len(v) for v in by_sensor.values()]
    return sum(means) / len(means), len(means)
