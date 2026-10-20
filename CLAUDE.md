# Distributed Boiler Monitoring (MQTT): Monitoramento de Caldeira

Contexto: trabalho acadêmico (pós-graduação). Sensores de temperatura enviam dados a cada 60 s a um broker MQTT. O serviço CAT calcula a média dos últimos 120 s e publica eventos. O serviço Alarms exibe os alarmes em uma interface gráfica. Ao menos um sensor deve ser real (app de smartphone com React Native + Expo).

O plano completo está em `plano-projeto-mqtt.md`. Siga-o como fonte da verdade (tópicos, payloads, estrutura de pastas, fases).

## Regras do projeto

- Broker: Mosquitto 2.x, listeners 1883 (MQTT) e 9001 (WebSocket). MQTT "raiz", sem camadas proprietárias.
- Serviços em Python 3.12 com `paho-mqtt`, cada um em sua pasta (`sensors-sim`, `cat-service`, `alarms-service`) com Dockerfile próprio.
- Alarms: painel web (FastAPI + SSE + Chart.js) em `http://localhost:8080`. Também imprime no console.
- App: `mobile-app/` (Expo, `paho-mqtt` via WebSocket). Roda no host, fora do Docker.
- Dentro do Compose, o host do broker é `mosquitto`, nunca `localhost`.
- Configuração por variáveis de ambiente (`.env`): intervalos, janela e limiares nunca ficam fixos no código.
- Lógica separada de I/O: janela/médias/regras do CAT em módulo puro, com testes unitários.
- O buffer do CAT é acessado por threads diferentes: proteja com `threading.Lock`.
- Last Will obrigatório em `/status` (`offline`), com `online` publicado com `retain`.

## Tópicos e payloads

Ver seção 2 de `plano-projeto-mqtt.md`. Prefixo: `plant/boiler1/`.

## Comandos úteis

```bash
docker compose up -d --build
docker compose up -d --scale sensors=5
docker compose logs -f cat
mosquitto_sub -h localhost -t "plant/#" -v
cd mobile-app && npx expo start
```

## Forma de trabalhar

- Implemente uma fase do plano por vez e confirme o critério de pronto antes de seguir.
- Durante o desenvolvimento use `SENSOR_INTERVAL=5` e janelas proporcionais; volte a 60/120 s na entrega.
- Não instale nada globalmente no sistema sem avisar.
