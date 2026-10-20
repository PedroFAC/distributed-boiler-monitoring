import Slider from '@react-native-community/slider';
import { useKeepAwake } from 'expo-keep-awake';
import { LightSensor } from 'expo-sensors';
import { StatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';

import { connectSensor } from './src/mqtt';
import {
  DEFAULT_INTERVAL_S,
  DEFAULT_PORT,
  HEAT_MAX,
  luxToTemperature,
} from './src/sensor';

const MAX_LOG = 20;

function Sensor() {
  useKeepAwake();

  const [host, setHost] = useState('192.168.0.10');
  const [port, setPort] = useState(String(DEFAULT_PORT));
  const [sensorId, setSensorId] = useState('phone-01');
  const [intervalS, setIntervalS] = useState(String(DEFAULT_INTERVAL_S));
  const [status, setStatus] = useState('desconectado');
  const [lux, setLux] = useState(null);
  const [heat, setHeat] = useState(0);
  const [log, setLog] = useState([]);

  const conn = useRef(null);
  const timer = useRef(null);
  const latest = useRef({ lux: 0, heat: 0 });

  const temperature = luxToTemperature(lux, heat);
  latest.current = { lux, heat };

  useEffect(() => {
    const sub = LightSensor.addListener(({ illuminance }) => setLux(illuminance));
    LightSensor.setUpdateInterval(1000);
    return () => sub.remove();
  }, []);

  const addLog = useCallback((line) => {
    setLog((prev) => [line, ...prev].slice(0, MAX_LOG));
  }, []);

  const publish = useCallback(() => {
    if (!conn.current) return;
    const { lux: l, heat: h } = latest.current;
    const p = conn.current.publishReading(luxToTemperature(l, h));
    addLog(`${new Date(p.ts * 1000).toLocaleTimeString()}  ${p.value.toFixed(1)} °C`);
  }, [addLog]);

  const disconnect = useCallback(() => {
    clearInterval(timer.current);
    timer.current = null;
    conn.current?.disconnect();
    conn.current = null;
    setStatus('desconectado');
  }, []);

  const connect = () => {
    disconnect();
    setStatus('conectando...');
    const period = Math.max(1, Number(intervalS) || DEFAULT_INTERVAL_S) * 1000;
    conn.current = connectSensor({
      host: host.trim(),
      port: Number(port) || DEFAULT_PORT,
      sensorId: sensorId.trim(),
      onConnect: () => {
        setStatus('conectado');
        publish();
        timer.current = setInterval(publish, period);
      },
      onLost: () => {
        clearInterval(timer.current);
        timer.current = null;
        conn.current = null;
        setStatus('conexão perdida');
      },
      onError: (e) => {
        conn.current = null;
        setStatus(`falha: ${e.errorMessage ?? 'erro'}`);
      },
    });
  };

  useEffect(() => disconnect, [disconnect]);

  const connected = status === 'conectado';

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.title}>Sensor da caldeira</Text>

        <Text style={styles.label}>IP do broker</Text>
        <TextInput
          style={styles.input}
          value={host}
          onChangeText={setHost}
          autoCapitalize="none"
          keyboardType="numbers-and-punctuation"
          editable={!connected}
        />
        <View style={styles.row}>
          <View style={styles.flex}>
            <Text style={styles.label}>Porta (WebSocket)</Text>
            <TextInput
              style={styles.input}
              value={port}
              onChangeText={setPort}
              keyboardType="number-pad"
              editable={!connected}
            />
          </View>
          <View style={styles.flex}>
            <Text style={styles.label}>Intervalo (s)</Text>
            <TextInput
              style={styles.input}
              value={intervalS}
              onChangeText={setIntervalS}
              keyboardType="number-pad"
              editable={!connected}
            />
          </View>
        </View>
        <Text style={styles.label}>ID do sensor</Text>
        <TextInput
          style={styles.input}
          value={sensorId}
          onChangeText={setSensorId}
          autoCapitalize="none"
          editable={!connected}
        />

        <View style={styles.row}>
          <View style={[styles.dot, connected ? styles.on : styles.off]} />
          <Text style={styles.flex}>{status}</Text>
          <Pressable
            style={[styles.button, connected && styles.buttonStop]}
            onPress={connected ? disconnect : connect}>
            <Text style={styles.buttonText}>{connected ? 'Desconectar' : 'Conectar'}</Text>
          </Pressable>
        </View>

        <Text style={styles.reading}>{temperature.toFixed(1)} °C</Text>
        <Text style={styles.hint}>
          Luminosidade: {lux == null ? 'indisponível (só Android)' : `${Math.round(lux)} lx`}
        </Text>

        <Text style={styles.label}>Aquecimento: +{heat.toFixed(0)} °C</Text>
        <Slider
          minimumValue={0}
          maximumValue={HEAT_MAX}
          step={1}
          value={heat}
          onValueChange={setHeat}
        />

        <Text style={styles.label}>Últimas publicações</Text>
        {log.length === 0 && <Text style={styles.hint}>nenhuma ainda</Text>}
        {log.map((line, i) => (
          <Text key={`${i}-${line}`} style={styles.logLine}>
            {line}
          </Text>
        ))}
      </ScrollView>
      <StatusBar style="auto" />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#fff' },
  container: { padding: 16, paddingTop: 48, gap: 6 },
  title: { fontSize: 22, fontWeight: '700', marginBottom: 8 },
  label: { fontSize: 13, color: '#555', marginTop: 8 },
  input: { borderWidth: 1, borderColor: '#ccc', borderRadius: 6, padding: 8, fontSize: 16 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 8 },
  flex: { flex: 1 },
  dot: { width: 12, height: 12, borderRadius: 6 },
  on: { backgroundColor: '#2e9e4f' },
  off: { backgroundColor: '#b33' },
  button: { backgroundColor: '#1a73e8', paddingVertical: 10, paddingHorizontal: 16, borderRadius: 6 },
  buttonStop: { backgroundColor: '#b33' },
  buttonText: { color: '#fff', fontWeight: '600' },
  reading: { fontSize: 48, fontWeight: '700', textAlign: 'center', marginTop: 16 },
  hint: { color: '#777', textAlign: 'center' },
  logLine: { fontFamily: 'monospace', fontSize: 13 },
});

export default function App() {
  return (
    <SafeAreaProvider>
      <Sensor />
    </SafeAreaProvider>
  );
}
