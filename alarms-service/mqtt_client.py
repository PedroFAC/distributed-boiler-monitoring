import os
import time

import paho.mqtt.client as mqtt

from state import PREFIX

MQTT_HOST = os.environ.get("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))

SUBSCRIPTIONS = [
    f"{PREFIX}/events/#",
    f"{PREFIX}/cat/average",
    f"{PREFIX}/sensors/+/status",
]


def console_listener(change):
    """Mantém a saída no console: [ALARME] 14:32:10 | TEMPERATURA ALTA | média = 213.5 °C"""
    if change["kind"] != "alarm":
        return
    a = change["data"]
    hora = time.strftime("%H:%M:%S", time.localtime(a["ts"]))
    linha = f"[ALARME] {hora} | {a['label']} | média = {a['avg']:.1f} °C"
    if a["prev_avg"] is not None:
        linha += f" (anterior = {a['prev_avg']:.1f} °C)"
    print(linha, flush=True)


def create_client(state):
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="alarms-service")
    client.reconnect_delay_set(min_delay=1, max_delay=10)

    def on_connect(c, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print(f"[alarms] falha ao conectar: {reason_code}", flush=True)
            return
        print(f"[alarms] conectado a {MQTT_HOST}:{MQTT_PORT}", flush=True)
        # Assina aqui para reassinar após reconexões.
        c.subscribe([(topic, 1) for topic in SUBSCRIPTIONS])
        state.set_broker_connected(True)

    def on_disconnect(c, userdata, flags, reason_code, properties):
        print(f"[alarms] desconectado: {reason_code}", flush=True)
        state.set_broker_connected(False)

    def on_message(c, userdata, msg):
        state.handle_message(msg.topic, msg.payload, time.time())

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    return client


def start(client):
    client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=30)
    client.loop_start()


def stop(client):
    client.disconnect()
    client.loop_stop()
