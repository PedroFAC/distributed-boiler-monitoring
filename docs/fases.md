# Andamento por fase

| Fase | Descrição | Estado |
|---|---|---|
| 1 | Broker e infraestrutura | Concluída |
| 2 | Sensores simulados | Concluída |
| 3 | Serviço CAT | Concluída |
| 4 | Serviço Alarms com interface gráfica | Concluída |
| 5 | Aplicativo Expo (sensor real) | Pendente |
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

## Fase 5: Aplicativo Expo (pendente)

Planejado: app React Native + Expo em `mobile-app/`, conectado por WebSocket (porta 9001), publicando um sensor real (luminosidade ou barômetro convertido para a faixa de temperatura) com Last Will, `online` retido e slider de aquecimento. Pendência de confirmar com o professor se o sensor precisa ser a temperatura real da bateria, o que exige *development build*.

## Fase 6: Integração e entrega (pendente)

- Rodar tudo junto (broker, 3 sensores, CAT, Alarms e o app) e validar ponta a ponta.
- Testar entrada e saída de sensores e a recuperação do Last Will.
- Voltar `SENSOR_INTERVAL`, `CAT_WINDOW` e `CAT_PERIOD` para 60/120/60 e remover `SENSOR_BASE` e `SENSOR_NOISE`.
- Revisar este README para a entrega.
