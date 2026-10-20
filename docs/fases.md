# Andamento por fase

| Fase | Descrição | Estado |
|---|---|---|
| 1 | Broker e infraestrutura | Concluída |
| 2 | Sensores simulados | Concluída |
| 3 | Serviço CAT | Concluída |
| 4 | Serviço Alarms com interface gráfica | Concluída |
| 5 | Aplicativo Expo (sensor real) | Concluída |
| 6 | Integração, documentação e entrega | Pendente |

## Fase 1: Broker e infraestrutura

**Entregue:** estrutura de pastas, `mosquitto/mosquitto.conf`, `.env` e `docker-compose.yml` com o serviço `mosquitto` (portas 1883 e 9001, healthcheck).

**Critério de pronto:** mensagem publicada no host chega ao `mosquitto_sub`, e o healthcheck fica `healthy`.
**Resultado:** atendido. O WebSocket respondeu `101 Switching Protocols` no handshake; não foi testado com um cliente MQTT.js completo.

## Fase 2: Sensores simulados

**Entregue:** `sensors-sim/` (`sensor.py`, `Dockerfile` com `python:3.12-slim`, `requirements.txt`) e o serviço `sensors` no Compose.

Pontos principais: valor com ruído gaussiano e deriva opcional, modo `SPIKE`, `client_id` único, QoS 1, Last Will e `online` com retain.

**Critério de pronto:** `docker compose up -d --scale sensors=3` mostra três sensores publicando.
**Resultado:** atendido. Também verificado: após `docker kill` em um sensor, o broker publicou `offline` (Last Will).

## Fase 3: Serviço CAT

**Entregue:** `cat-service/` com `window.py`, `rules.py`, `cat.py`, `Dockerfile` e 17 testes unitários.

Pontos principais: buffer com `Lock`, média das médias por sensor, `sudden_increase` por salto, `high_temperature` por transição, parâmetros vindos do `.env`.

**Critério de pronto:** com spike, o CAT publica o evento e o `mosquitto_sub -t "plant/boiler1/events/#"` o exibe.
**Resultado:** atendido. Com um sensor em spike (`SPIKE_STEP=30`), as médias foram 139,7 → 155,2 → 185,5 → 214,8 → 239,6 → 249,6, com um `sudden_increase` por ciclo e um único `high_temperature`.

## Fase 4: Serviço Alarms com interface gráfica

**Entregue:** `alarms-service/` com `state.py`, `mqtt_client.py`, `main.py`, `static/index.html`, `Dockerfile` e 10 testes unitários. Painel em <http://localhost:8080>.

**Critério de pronto:** o painel mostra média, sensores e alarmes atualizando em tempo real.
**Resultado:** atendido no servidor. O stream SSE entregou os alarmes do teste de spike, o console imprimiu no formato do plano e o botão de limpar funcionou. O visual da página (layout, gráfico, banner, som) ainda precisa de conferência no navegador.

**Ajuste de desenvolvimento:** para gerar mais alarmes sem alterar os limiares, `SENSOR_BASE=195` e `SENSOR_NOISE=12` no `.env`. Com 3 sensores, saíram 7 eventos em 65 s.

## Fase 5: Aplicativo Expo (sensor real)

**Entregue:** `mobile-app/` com `App.js` (tela), `src/sensor.js` (conversão luminosidade → temperatura e payload, sem React nem MQTT) e `src/mqtt.js` (conexão `paho-mqtt` por WebSocket, Last Will e publicação). A tela tem IP, porta, intervalo e ID editáveis, botão conectar/desconectar com indicador, leitura atual, slider de aquecimento (+0 a +60 °C), log das últimas 20 publicações e `expo-keep-awake`.

**Critério de pronto:** o celular aparece como online no painel e o slider provoca o evento de aumento repentino.
**Resultado:** atendido, testado manualmente em um celular e em um tablet com o Expo Go.

**Decisões e ajustes:**
- O projeto usa o **SDK 57**, porque é o que o Expo Go instalado no celular suporta (o template tinha vindo com o SDK 58).
- `SafeAreaView` vem de `react-native-safe-area-context`, pois o do React Native está obsoleto.
- Ao desconectar pelo botão, o app publica `offline` antes de fechar, já que uma desconexão limpa não dispara o Last Will.
- Sensor: luminosidade (só Android). A temperatura real da bateria exigiria *development build* e continua como pendência a confirmar com o professor.
- Não há teste automatizado do app.

## Fase 6: Integração e entrega (pendente)

- Rodar tudo junto (broker, 3 sensores, CAT, Alarms e o app) e validar ponta a ponta.
- Testar entrada e saída de sensores e a recuperação do Last Will.
- Voltar `SENSOR_INTERVAL`, `CAT_WINDOW` e `CAT_PERIOD` para 60/120/60 e remover `SENSOR_BASE` e `SENSOR_NOISE`.
- Revisar este README para a entrega.
