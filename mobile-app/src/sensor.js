// Lógica pura do sensor (sem React nem MQTT), para facilitar testes.

export const DEFAULT_PORT = 9001;
export const DEFAULT_INTERVAL_S = 60;
export const DEFAULT_BASE = 180; // °C, alinhado ao SENSOR_BASE dos simulados
export const LIGHT_RANGE = 20; // °C somados a partir da luminosidade
export const HEAT_MAX = 60; // °C do slider de aquecimento
const LUX_MAX = 10000;

export const temperatureTopic = (id) => `plant/boiler1/sensors/${id}/temperature`;
export const statusTopic = (id) => `plant/boiler1/sensors/${id}/status`;

// O expo-sensors não expõe temperatura: a luminosidade (escala log) é
// convertida para 0..LIGHT_RANGE °C e somada à base e ao aquecimento forçado.
export function luxToTemperature(lux, heat = 0, base = DEFAULT_BASE) {
  const l = Math.max(0, lux ?? 0);
  const factor = Math.min(1, Math.log10(l + 1) / Math.log10(LUX_MAX + 1));
  return base + factor * LIGHT_RANGE + heat;
}

export function buildPayload(sensorId, value, now = Date.now()) {
  return {
    sensor_id: sensorId,
    value: Math.round(value * 100) / 100,
    unit: 'C',
    ts: Math.floor(now / 1000),
    source: 'phone-light',
  };
}
