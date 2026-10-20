import Paho from 'paho-mqtt';

import { buildPayload, statusTopic, temperatureTopic } from './sensor';

function message(topic, payload, retained = false) {
  const msg = new Paho.Message(payload);
  msg.destinationName = topic;
  msg.qos = 1;
  msg.retained = retained;
  return msg;
}

// Conexão MQTT sobre WebSocket com Last Will em /status.
export function connectSensor({ host, port, sensorId, onConnect, onLost, onError }) {
  const client = new Paho.Client(host, port, `${sensorId}-${Date.now()}`);

  client.onConnectionLost = (res) => onLost?.(res);

  client.connect({
    useSSL: false,
    timeout: 5,
    keepAliveInterval: 30,
    willMessage: message(statusTopic(sensorId), 'offline', true),
    onSuccess: () => {
      client.send(message(statusTopic(sensorId), 'online', true));
      onConnect?.();
    },
    onFailure: (e) => onError?.(e),
  });

  return {
    publishReading(value) {
      const payload = buildPayload(sensorId, value);
      client.send(message(temperatureTopic(sensorId), JSON.stringify(payload)));
      return payload;
    },
    disconnect() {
      try {
        // Desconexão limpa não dispara o Last Will: publica offline antes.
        if (client.isConnected()) {
          client.send(message(statusTopic(sensorId), 'offline', true));
          client.disconnect();
        }
      } catch (e) {
        // já desconectado
      }
    },
  };
}
