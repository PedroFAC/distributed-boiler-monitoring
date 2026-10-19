"""Estado do painel de alarmes e interpretação das mensagens MQTT. Sem I/O de rede."""

import json
import threading
from collections import deque

PREFIX = "plant/boiler1"

# tipo de evento -> (rótulo, severidade)
EVENT_INFO = {
    "high_temperature": ("TEMPERATURA ALTA", "high"),
    "sudden_increase": ("AUMENTO REPENTINO", "warning"),
}


class AlarmsState:
    """Guarda alarmes, histórico de médias e sensores. Acessado por threads
    diferentes (MQTT e servidor web), então tudo passa pelo Lock.

    Os listeners são chamados com o Lock preso e precisam ser rápidos e não
    bloqueantes (o servidor usa call_soon_threadsafe).
    """

    def __init__(self, high_threshold, max_alarms=50, max_history=200):
        self._lock = threading.Lock()
        self._high_threshold = high_threshold
        self._max_alarms = max_alarms
        self._max_history = max_history
        self._alarms = deque(maxlen=max_alarms)
        self._history = deque(maxlen=max_history)
        self._last_average = None
        self._sensors = {}
        self._broker_connected = False
        self._next_id = 1
        self._listeners = []

    # --- assinatura de mudanças ---

    def subscribe(self, listener):
        """Registra o listener e devolve o snapshot atual, de forma atômica."""
        with self._lock:
            self._listeners.append(listener)
            return self._snapshot_locked()

    def unsubscribe(self, listener):
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def _emit(self, kind, data):
        for listener in list(self._listeners):
            try:
                listener({"kind": kind, "data": data})
            except Exception as exc:  # um listener ruim não pode derrubar a thread MQTT
                print(f"[alarms] erro em listener: {exc}")

    # --- leitura ---

    def snapshot(self):
        with self._lock:
            return self._snapshot_locked()

    def _snapshot_locked(self):
        return {
            "config": {
                "high_threshold": self._high_threshold,
                "max_alarms": self._max_alarms,
                "max_history": self._max_history,
            },
            "broker_connected": self._broker_connected,
            "last_average": self._last_average,
            "history": list(self._history),
            "alarms": list(reversed(self._alarms)),  # mais recente primeiro
            "sensors": [
                {"id": sid, **info} for sid, info in sorted(self._sensors.items())
            ],
        }

    # --- escrita ---

    def set_broker_connected(self, connected):
        with self._lock:
            if self._broker_connected == connected:
                return
            self._broker_connected = connected
            self._emit("connection", {"broker_connected": connected})

    def clear_alarms(self):
        with self._lock:
            self._alarms.clear()
            self._emit("clear", {})

    def handle_message(self, topic, payload, now):
        """Interpreta uma mensagem MQTT. `now` (epoch s) marca o recebimento
        de status de sensores."""
        parts = topic.split("/")
        if parts[:2] != PREFIX.split("/"):
            return
        rest = parts[2:]
        if rest == ["cat", "average"]:
            self._handle_average(payload)
        elif len(rest) == 2 and rest[0] == "events":
            self._handle_event(rest[1], payload)
        elif len(rest) == 3 and rest[0] == "sensors" and rest[2] == "status":
            self._handle_status(rest[1], payload, now)

    def _handle_average(self, payload):
        data = _parse_json(payload)
        try:
            avg = float(data["avg"])
            ts = int(data["ts"])
        except (TypeError, KeyError, ValueError):
            print(f"[alarms] média inválida: {payload!r}")
            return
        with self._lock:
            self._last_average = data
            self._history.append({"ts": ts, "avg": avg})
            self._emit("average", {"last": data, "point": {"ts": ts, "avg": avg}})

    def _handle_event(self, name, payload):
        if name not in EVENT_INFO:
            return
        data = _parse_json(payload)
        try:
            avg = float(data["avg"])
            ts = int(data["ts"])
        except (TypeError, KeyError, ValueError):
            print(f"[alarms] evento inválido: {payload!r}")
            return
        label, severity = EVENT_INFO[name]
        with self._lock:
            alarm = {
                "id": self._next_id,
                "type": name,
                "label": label,
                "severity": severity,
                "avg": avg,
                "prev_avg": data.get("prev_avg"),
                "ts": ts,
            }
            self._next_id += 1
            self._alarms.append(alarm)
            self._emit("alarm", alarm)

    def _handle_status(self, sensor_id, payload, now):
        status = payload.decode("utf-8", errors="replace").strip()
        if status not in ("online", "offline"):
            return
        with self._lock:
            info = {"status": status, "ts": int(now)}
            self._sensors[sensor_id] = info
            self._emit("sensor", {"id": sensor_id, **info})


def _parse_json(payload):
    try:
        return json.loads(payload)
    except ValueError:
        return None
