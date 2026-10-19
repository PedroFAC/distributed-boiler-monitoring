import json
import os
import random
import signal
import socket
import threading
import time

import paho.mqtt.client as mqtt

MQTT_HOST = os.environ.get("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
SENSOR_INTERVAL = float(os.environ.get("SENSOR_INTERVAL", "60"))
SENSOR_ID = os.environ.get("SENSOR_ID") or f"sim-{socket.gethostname()}"

# Modelo da leitura: base + deriva lenta + ruído gaussiano.
SENSOR_BASE = float(os.environ.get("SENSOR_BASE", "80"))
SENSOR_NOISE = float(os.environ.get("SENSOR_NOISE", "1.0"))
SENSOR_DRIFT = float(os.environ.get("SENSOR_DRIFT", "0"))  # °C por leitura

# Aquecimento forçado: a cada leitura soma SPIKE_STEP ao valor, até SPIKE_MAX.
SPIKE = os.environ.get("SPIKE", "false").lower() in ("1", "true", "yes")
SPIKE_STEP = float(os.environ.get("SPIKE_STEP", "10"))
SPIKE_MAX = float(os.environ.get("SPIKE_MAX", "250"))

TOPIC_PREFIX = f"plant/boiler1/sensors/{SENSOR_ID}"
TOPIC_TEMP = f"{TOPIC_PREFIX}/temperature"
TOPIC_STATUS = f"{TOPIC_PREFIX}/status"

stop = threading.Event()

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=SENSOR_ID)
client.will_set(TOPIC_STATUS, "offline", qos=1, retain=True)
client.reconnect_delay_set(min_delay=1, max_delay=10)


def on_connect(c, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"[{SENSOR_ID}] falha ao conectar: {reason_code}")
        return
    print(f"[{SENSOR_ID}] conectado a {MQTT_HOST}:{MQTT_PORT}")
    c.publish(TOPIC_STATUS, "online", qos=1, retain=True)


def on_disconnect(c, userdata, flags, reason_code, properties):
    print(f"[{SENSOR_ID}] desconectado: {reason_code}")


client.on_connect = on_connect
client.on_disconnect = on_disconnect


def handle_stop(signum, frame):
    stop.set()


signal.signal(signal.SIGTERM, handle_stop)
signal.signal(signal.SIGINT, handle_stop)


def main():
    client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=30)
    client.loop_start()

    drift = 0.0
    spike = 0.0
    while not stop.is_set():
        drift += SENSOR_DRIFT
        if SPIKE:
            spike = min(spike + SPIKE_STEP, SPIKE_MAX - SENSOR_BASE)
        value = SENSOR_BASE + drift + spike + random.gauss(0, SENSOR_NOISE)
        payload = {
            "sensor_id": SENSOR_ID,
            "value": round(value, 2),
            "unit": "C",
            "ts": int(time.time()),
            "source": "simulated",
        }
        if client.is_connected():
            client.publish(TOPIC_TEMP, json.dumps(payload), qos=1)
            print(f"[{SENSOR_ID}] {payload['value']} °C")
        stop.wait(SENSOR_INTERVAL)

    # Desconexão limpa não dispara o Last Will, então publica offline à mão.
    if client.is_connected():
        client.publish(TOPIC_STATUS, "offline", qos=1, retain=True).wait_for_publish(2)
    client.disconnect()
    client.loop_stop()


if __name__ == "__main__":
    main()
