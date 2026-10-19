# Roteiro de testes

## Testes unitários (host, sem Docker)

```bash
(cd cat-service && python3 -m unittest discover -s tests -v)
(cd alarms-service && python3 -m unittest discover -s tests -v)
```

| Suíte | Testes | Cobre |
|---|---|---|
| `cat-service/tests/test_window.py` | 7 | Média das médias por sensor, descarte de leituras antigas, borda da janela, cópia no snapshot, escrita concorrente |
| `cat-service/tests/test_rules.py` | 10 | Salto exato no limiar, queda, primeira média, limiar estrito de 200, disparo só na transição, rearme |
| `alarms-service/tests/test_state.py` | 10 | Tipos e severidades, limite de alarmes e histórico, payloads inválidos, tópicos alheios, status de sensores, limpar, eventos de conexão |

## Testes de integração (com os containers de pé)

Todos podem rodar com o ambiente em execução. Os clientes `mosquitto_*` abaixo usam o container, então não precisam estar instalados no host.

### 1. Broker: publicar e assinar

```bash
docker compose exec mosquitto mosquitto_sub -h localhost -t "plant/#" -v      # terminal 1
docker compose exec mosquitto mosquitto_pub -h localhost -t "plant/test" -m "ola"   # terminal 2
```
**Esperado:** o terminal 1 mostra `plant/test ola`. Use `plant/test` para não interferir nos dados dos sensores.

### 2. Sensores simulados

```bash
docker compose up -d --scale sensors=3
docker compose exec mosquitto mosquitto_sub -h localhost -t "plant/boiler1/sensors/#" -v
```
**Esperado:** três IDs `sim-...` publicando `temperature`, e o `status` `online` retido chegando logo ao assinar.

### 3. Last Will

```bash
docker kill <nome-de-um-container-sensors>
docker compose exec mosquitto mosquitto_sub -h localhost -t "plant/boiler1/sensors/+/status" -v -W 3
```
**Esperado:** o sensor morto aparece como `offline`, publicado pelo broker. (O `restart: unless-stopped` religa o container depois.)

### 4. Spike: aumento repentino e temperatura alta

Com os sensores normais perto de 80 °C, a média de 3 sensores + 1 em spike não passa de 200 °C. Pare os normais para ver o `high_temperature`:

```bash
docker compose up -d --scale sensors=0
docker run --rm --network mqtt-boiler_default --env-file .env \
  -e SPIKE=true -e SPIKE_STEP=30 -e SENSOR_ID=spike-test mqtt-boiler-sensors
docker compose up -d --scale sensors=3        # restaura
```
Em outro terminal: `docker compose logs -f cat` e `docker compose logs -f alarms`.

**Esperado:**
- Um `sudden_increase` por ciclo enquanto a média sobe mais de 5 °C.
- **Um único** `high_temperature`, no ciclo em que a média passa de 200 °C.
- Estabilizada em ~249 °C, nenhum evento novo.
- No console do Alarms: `[ALARME] hh:mm:ss | TEMPERATURA ALTA | média = 215.2 °C (anterior = 184.1 °C)`.
- Ao encerrar (Ctrl+C), `spike-test` fica `offline`; depois da janela vazia e do retorno dos sensores, uma queda de ~170 °C gera mais um `sudden_increase`.

### 5. Painel web

Abrir <http://localhost:8080> durante o teste 4.

**Esperado:** o cabeçalho mostra "Broker conectado"; a média e o gráfico se atualizam a cada ciclo; os sensores aparecem na lista; cada alarme entra no topo da lista com cor por severidade e abre o banner; "Limpar alarmes" esvazia a lista.

Também é possível inspecionar a API:

```bash
curl -s localhost:8080/api/state | python3 -m json.tool
curl -N localhost:8080/api/stream
curl -X POST localhost:8080/api/alarms/clear
```

## Resultados registrados

Testes executados durante o desenvolvimento:

| Teste | Resultado |
|---|---|
| Unitários CAT (17) e Alarms (10) | Passaram |
| Pub/sub no broker | Passou |
| Handshake WebSocket na porta 9001 | Passou (101) |
| 3 sensores publicando | Passou |
| Last Will após `docker kill` | Passou |
| Spike com CAT e eventos | Passou |
| SSE do Alarms, console e botão de limpar | Passaram |
| Visual do painel no navegador | **Não verificado** |
| Cliente MQTT.js completo no WebSocket | **Não testado** |
