import json
import math
import os
import signal
import threading
import time

import paho.mqtt.client as mqtt

from rules import AlarmRules
from window import ReadingBuffer, compute_average

MQTT_HOST = os.environ.get("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
CAT_WINDOW = float(os.environ.get("CAT_WINDOW", "120"))
CAT_PERIOD = float(os.environ.get("CAT_PERIOD", "60"))
CAT_JUMP_THRESHOLD = float(os.environ.get("CAT_JUMP_THRESHOLD", "5"))
CAT_HIGH_THRESHOLD = float(os.environ.get("CAT_HIGH_THRESHOLD", "200"))

TOPIC_SENSORS = "plant/boiler1/sensors/+/temperature"
TOPIC_AVERAGE = "plant/boiler1/cat/average"
TOPIC_EVENT = "plant/boiler1/events/{}"

buffer = ReadingBuffer(CAT_WINDOW)
rules = AlarmRules(CAT_JUMP_THRESHOLD, CAT_HIGH_THRESHOLD)
stop = threading.Event()

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="cat-service")
client.reconnect_delay_set(min_delay=1, max_delay=10)


def on_connect(c, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"[cat] falha ao conectar: {reason_code}")
        return
    print(f"[cat] conectado a {MQTT_HOST}:{MQTT_PORT}")
    # Assina aqui para reassinar após reconexões.
    c.subscribe(TOPIC_SENSORS, qos=1)


def on_message(c, userdata, msg):
    try:
        data = json.loads(msg.payload)
        sensor_id = str(data["sensor_id"])
        value = float(data["value"])
    except (ValueError, KeyError, TypeError):
        print(f"[cat] payload inválido em {msg.topic}: {msg.payload!r}")
        return
    if not math.isfinite(value):
        return
    # Usa o horário de chegada, não o ts do payload: relógios de sensores
    # (celular) podem estar defasados.
    buffer.add(time.time(), sensor_id, value)


client.on_connect = on_connect
client.on_message = on_message


def publish(topic, payload):
    client.publish(topic, json.dumps(payload), qos=1)


def cycle(prev_avg):
    """Um ciclo do timer. Devolve a média atual (ou prev_avg se a janela está vazia)."""
    now = time.time()
    result = compute_average(buffer.snapshot(now))
    if result is None:
        print("[cat] janela vazia, nada a publicar")
        return prev_avg
    avg, n_sensors = result
    ts = int(now)
    publish(TOPIC_AVERAGE, {
        "avg": round(avg, 2),
        "prev_avg": None if prev_avg is None else round(prev_avg, 2),
        "sensors": n_sensors,
        "window_s": int(CAT_WINDOW),
        "ts": ts,
    })
    print(f"[cat] média = {avg:.2f} °C ({n_sensors} sensores)")
    for event in rules.evaluate(avg, prev_avg):
        publish(TOPIC_EVENT.format(event), {
            "type": event,
            "avg": round(avg, 2),
            "prev_avg": None if prev_avg is None else round(prev_avg, 2),
            "ts": ts,
        })
        print(f"[cat] EVENTO {event} (média = {avg:.2f}, anterior = {prev_avg})")
    return avg


def main():
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())

    client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=30)
    client.loop_start()

    prev_avg = None
    while not stop.wait(CAT_PERIOD):
        if client.is_connected():
            prev_avg = cycle(prev_avg)

    client.disconnect()
    client.loop_stop()


if __name__ == "__main__":
    main()
