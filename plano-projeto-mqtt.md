# Plano de Implementação: Projeto MQTT (Monitoramento de Caldeira)

## 1. Escopo e decisões

| Item | Decisão |
|---|---|
| Broker | Mosquitto 2.x (MQTT "raiz"), com listener TCP 1883 e WebSocket 9001 |
| Sensores simulados | Python + `paho-mqtt` (escaláveis via Docker Compose) |
| Serviço CAT | Python + `paho-mqtt` |
| Serviço Alarms + interface gráfica (obrigatória) | Python + `paho-mqtt` + painel web (FastAPI + SSE + Chart.js) |
| Sensor real (pós) | App smartphone com React Native + Expo, via MQTT sobre WebSocket |
| Infraestrutura | Docker + Compose para broker e serviços; Expo roda direto no Ubuntu (host) |

### Por que esta divisão entre Docker e host

- **Docker (compose):** Mosquitto, sensores, CAT e Alarms. Sobe tudo com um comando, é reprodutível e permite escalar sensores com `--scale`.
- **Expo no host:** o Metro bundler precisa ser alcançado pelo celular na rede local, e o QR code do Expo Go depende do IP real da máquina. Dentro de container isso exige `network_mode: host` e ajustes de hostname, sem ganho real. Rodar no host é mais simples e estável.
- **Interface do Alarms:** `tkinter` dentro de container exige encaminhar o X11, o que é frágil. Por isso a interface é um **painel web**, que funciona bem em container (acesso em `http://localhost:8080`). Se preferir `tkinter`, o serviço Alarms roda no host e os demais no Docker.

---

## 2. Arquitetura

```
[Sensores simulados (N containers)] ─┐
                                     ├─► [Mosquitto] ─► [CAT] ─► publica eventos ─► [Mosquitto] ─► [Alarms + Painel Web]
[App Expo no celular (WS :9001)]  ───┘
```

### Tópicos

| Tópico | Publicador | Descrição |
|---|---|---|
| `plant/boiler1/sensors/<sensor_id>/temperature` | Sensores / App | Leitura de temperatura (a cada 60 s) |
| `plant/boiler1/sensors/<sensor_id>/status` | Sensores / App | `online` (retain) e `offline` (Last Will) |
| `plant/boiler1/cat/average` | CAT | Média da janela de 120 s |
| `plant/boiler1/events/sudden_increase` | CAT | Aumento repentino (médias consecutivas diferem em 5 °C ou mais) |
| `plant/boiler1/events/high_temperature` | CAT | Temperatura alta (média acima de 200 °C) |

### Payloads (JSON)

Leitura:
```json
{"sensor_id": "sim-03", "value": 87.4, "unit": "C", "ts": 1760000000, "source": "simulated"}
```

Média (CAT):
```json
{"avg": 143.2, "prev_avg": 141.0, "sensors": 5, "window_s": 120, "ts": 1760000060}
```

Evento:
```json
{"type": "high_temperature", "avg": 213.5, "prev_avg": 198.0, "ts": 1760000060}
```

---

## 3. Estrutura do repositório

```
distributed-boiler-monitoring/
├── docker-compose.yml
├── .env
├── mosquitto/
│   └── mosquitto.conf
├── sensors-sim/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── sensor.py
├── cat-service/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── cat.py
├── alarms-service/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py            # assina o MQTT e expõe SSE
│   ├── mqtt_client.py     # lógica de mensagens, separada da UI
│   └── static/
│       └── index.html     # painel (Chart.js)
├── mobile-app/            # projeto Expo (fora do Docker)
└── README.md
```

---

## 4. Preparação do ambiente (Ubuntu 22.04)

### 4.1 Pacotes básicos

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl build-essential ca-certificates gnupg mosquitto-clients
```

`mosquitto-clients` fornece `mosquitto_sub` e `mosquitto_pub` para depurar no terminal.

### 4.2 Docker Engine + Compose plugin

```bash
# Repositório oficial do Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
| sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Usar docker sem sudo (faça logout/login depois)
sudo usermod -aG docker $USER
```

Verificação:
```bash
docker --version
docker compose version
docker run --rm hello-world
```

### 4.3 Node.js via nvm (para o Expo)

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.bashrc
nvm install --lts
node -v && npm -v
```

> Não é necessário instalar `expo-cli` globalmente. Use `npx`.

### 4.4 Ajuste de file watchers (evita o erro `ENOSPC` no Metro)

```bash
echo "fs.inotify.max_user_watches=524288" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

### 4.5 Firewall (se o `ufw` estiver ativo)

```bash
sudo ufw allow 1883/tcp   # MQTT
sudo ufw allow 9001/tcp   # MQTT sobre WebSocket (app)
sudo ufw allow 8081/tcp   # Metro bundler (Expo)
sudo ufw allow 8080/tcp   # Painel do Alarms (opcional, para abrir de outro dispositivo)
```

### 4.6 Celular

1. Instalar o **Expo Go** (Play Store ou App Store).
2. Conectar o celular **na mesma rede Wi-Fi** do notebook.
3. Descobrir o IP do notebook: `hostname -I | awk '{print $1}'`.

> Redes de universidade costumam ter isolamento de clientes. Se o celular não alcançar o PC, use o hotspot do celular ou do notebook.

---

## 5. Docker Compose

### 5.1 `mosquitto/mosquitto.conf`

```
listener 1883
protocol mqtt

listener 9001
protocol websockets

allow_anonymous true
persistence false
```

### 5.2 `.env`

```
MQTT_HOST=mosquitto
MQTT_PORT=1883
SENSOR_INTERVAL=60
CAT_WINDOW=120
CAT_PERIOD=60
CAT_JUMP_THRESHOLD=5
CAT_HIGH_THRESHOLD=200
```

### 5.3 `docker-compose.yml`

```yaml
services:
  mosquitto:
    image: eclipse-mosquitto:2
    ports:
      - "1883:1883"
      - "9001:9001"
    volumes:
      - ./mosquitto/mosquitto.conf:/mosquitto/config/mosquitto.conf:ro
    healthcheck:
      test: ["CMD-SHELL", "mosquitto_sub -h localhost -t '$$SYS/#' -C 1 -W 3 || exit 1"]
      interval: 5s
      timeout: 5s
      retries: 10
    restart: unless-stopped

  cat:
    build: ./cat-service
    env_file: .env
    depends_on:
      mosquitto:
        condition: service_healthy
    restart: unless-stopped

  alarms:
    build: ./alarms-service
    env_file: .env
    ports:
      - "8080:8080"
    depends_on:
      mosquitto:
        condition: service_healthy
    restart: unless-stopped

  sensors:
    build: ./sensors-sim
    env_file: .env
    depends_on:
      mosquitto:
        condition: service_healthy
    # sem container_name e sem porta publicada, para permitir --scale
    restart: unless-stopped
```

### 5.4 Comandos do dia a dia

```bash
docker compose up -d --build                 # sobe tudo
docker compose up -d --scale sensors=5       # 5 sensores simulados
docker compose up -d --scale sensors=2       # reduz para 2 (número dinâmico)
docker compose logs -f cat                   # acompanha as médias
docker compose logs -f alarms
docker compose down
```

O `sensor_id` de cada réplica deve ser derivado do hostname do container (por exemplo, `sim-<hostname>`), para que cada instância tenha identidade e `client_id` únicos.

---

## 6. Fases de implementação

### Fase 1: Broker e infraestrutura (0,5 dia)

- [ ] Criar o repositório e a estrutura de pastas.
- [ ] Escrever `mosquitto.conf` e subir só o broker: `docker compose up -d mosquitto`.
- [ ] Testar do host:
  ```bash
  mosquitto_sub -h localhost -t "plant/#" -v
  mosquitto_pub -h localhost -t "plant/test" -m "ola"
  ```
- [ ] Testar o WebSocket (porta 9001) com um cliente simples, por exemplo um script MQTT.js.

**Critério de pronto:** mensagem publicada no host é recebida pelo `mosquitto_sub`, e o healthcheck do container fica `healthy`.

### Fase 2: Sensores simulados (0,5 dia)

- [ ] `sensor.py` com variáveis de ambiente (`MQTT_HOST`, `SENSOR_INTERVAL`).
- [ ] Valor = base + ruído gaussiano, com deriva lenta opcional.
- [ ] Modo de aquecimento forçado (`SPIKE` via variável de ambiente ou comando) para provocar os alarmes.
- [ ] `client_id` único, QoS 1, Last Will em `/status` (`offline`) e publicação de `online` com `retain` ao conectar.
- [ ] Para testes locais, usar `SENSOR_INTERVAL=5` e voltar a 60 na entrega.
- [ ] Dockerfile enxuto (`python:3.12-slim`, `pip install paho-mqtt`).

**Critério de pronto:** `docker compose up -d --scale sensors=3` mostra três sensores publicando em `plant/boiler1/sensors/+/temperature`.

### Fase 3: Serviço CAT (1 dia)

- [ ] Assinar `plant/boiler1/sensors/+/temperature`.
- [ ] Buffer `(timestamp, sensor_id, value)` protegido por `threading.Lock`, descartando leituras com mais de 120 s.
- [ ] A cada 60 s (timer), calcular a média da janela e publicar em `cat/average`.
- [ ] Regras de evento:
  - `|média_atual − média_anterior| ≥ 5` publica em `events/sudden_increase`.
  - `média_atual > 200` publica em `events/high_temperature`.
- [ ] Ignorar a comparação na primeira média (não há anterior).
- [ ] Evitar repetição do mesmo alarme a cada ciclo (alertar na transição, ou com um intervalo mínimo).
- [ ] Documentar a escolha: média de todas as leituras da janela ou média das médias por sensor.
- [ ] Parâmetros (`CAT_WINDOW`, `CAT_PERIOD`, limiares) vindos do `.env`.
- [ ] Testes unitários da lógica de janela e limiares, separados do MQTT.

**Critério de pronto:** com `--spike`, o CAT publica o evento correspondente e o `mosquitto_sub -t "plant/boiler1/events/#"` o exibe.

### Fase 4: Serviço Alarms com interface gráfica (1 dia)

**Backend (`main.py` + `mqtt_client.py`):**
- [ ] Assinar `plant/boiler1/events/#`, `plant/boiler1/cat/average` e `plant/boiler1/sensors/+/status`.
- [ ] Manter em memória os últimos N alarmes, a última média, o histórico de médias e os sensores online.
- [ ] Expor com FastAPI: `GET /` (página), `GET /api/state` (estado inicial) e `GET /api/stream` (SSE com novos eventos).
- [ ] Manter também a saída no console (`[ALARME] 14:32:10 | TEMPERATURA ALTA | média = 213.5 °C`).

**Frontend (`static/index.html`):**
- [ ] Cabeçalho com status da conexão ao broker.
- [ ] Cartão com a média atual e o número de sensores usados.
- [ ] Lista de sensores online/offline (a partir de `/status`).
- [ ] Gráfico da média ao longo do tempo (Chart.js) com a linha de 200 °C.
- [ ] Lista de alarmes com horário, tipo e valor, colorida por severidade (laranja: aumento repentino; vermelho: temperatura alta).
- [ ] Banner/popup e som ao chegar um alarme novo.
- [ ] Botão "Limpar alarmes".

**Alternativa tkinter:** rodar o Alarms no host (fora do compose). Usar `loop_start()` no paho, uma `queue.Queue` e `root.after(100, ...)` para atualizar a UI na thread principal, com `ttk.Treeview` para os alarmes e `matplotlib` para o gráfico.

**Critério de pronto:** abrir `http://localhost:8080` mostra a média, os sensores e os alarmes atualizando em tempo real.

### Fase 5: Aplicativo Expo (sensor real) (1 dia)

**Criação do projeto:**
```bash
cd mobile-app/..
npx create-expo-app@latest mobile-app
cd mobile-app
npx expo install expo-sensors expo-keep-awake
npm install paho-mqtt
npx expo start
```
Escanear o QR code com o Expo Go.

**Sobre o sensor:** o `expo-sensors` não expõe temperatura. Recomendação:
- Usar um sensor real (luminosidade no Android ou barômetro) convertido para uma faixa de "temperatura", e registrar `"source": "phone-light"` (ou similar) no payload.
- Incluir um **slider de aquecimento** para provocar os alarmes de forma controlada.
- Opção de maior fidelidade: temperatura da bateria (Android) via módulo nativo, que exige *development build* e não roda no Expo Go. Vale confirmar com o professor se isso é exigido.

**Tela do app:**
- [ ] Campo de IP do broker (editável) e porta 9001.
- [ ] ID do sensor, botão conectar/desconectar e indicador de conexão.
- [ ] Leitura atual, log das últimas publicações e slider de aquecimento.
- [ ] Publicação periódica (60 s, configurável) em `plant/boiler1/sensors/<id>/temperature`.
- [ ] Last Will em `/status` e publicação de `online` ao conectar.
- [ ] `expo-keep-awake` para manter a tela ligada.

**Conexão:**
```js
import Paho from 'paho-mqtt';

const client = new Paho.Client(host, 9001, `phone-${Date.now()}`);
client.connect({
  useSSL: false,
  onSuccess: () => setConnected(true),
  onFailure: (e) => console.log('falha', e),
});

const msg = new Paho.Message(JSON.stringify(payload));
msg.destinationName = `plant/boiler1/sensors/${id}/temperature`;
msg.qos = 1;
client.send(msg);
```

> Use o IP do notebook (`ws://<IP>:9001`), nunca `localhost`.

**Critério de pronto:** o celular aparece como online no painel do Alarms e o slider provoca o evento de aumento repentino.

### Fase 6: Integração, documentação e entrega (0,5 dia)

- [ ] Rodar o conjunto completo: broker, 3 sensores simulados, CAT, Alarms e o app.
- [ ] Validar o cenário de aumento repentino e de temperatura alta ponta a ponta.
- [ ] Testar entrada e saída de sensores (`--scale` e conectar/desconectar o app) e a recuperação do Last Will.
- [ ] README com diagrama, tabela de tópicos, formato dos payloads, pré-requisitos (seção 4 deste plano), comandos de execução e decisões de projeto.
- [ ] Voltar `SENSOR_INTERVAL` para 60 s e conferir os limiares.

---

## 7. Cronograma

| Etapa | Tempo |
|---|---|
| Ambiente (Ubuntu, Docker, Node, Expo Go) | 0,5 dia |
| Broker + sensores simulados | 1 dia |
| CAT | 1 dia |
| Alarms + interface gráfica | 1 dia |
| App Expo | 1 dia |
| Integração + README | 0,5 dia |
| **Total** | **cerca de 5 dias** |

---

## 8. Riscos e cuidados

- **Celular não conecta ao broker:** firewall, IP incorreto ou Wi-Fi com isolamento de clientes. Alternativa: hotspot.
- **Mosquitto 2.x recusa conexões externas:** garanta `listener` explícito e `allow_anonymous true` no `mosquitto.conf`.
- **Containers não enxergam `localhost`:** dentro do Compose use o nome do serviço (`mosquitto`), não `localhost`.
- **Serviços sobem antes do broker:** use `depends_on` com `condition: service_healthy` e reconexão automática no cliente paho.
- **Janela de 120 s com envio a cada 60 s** dá só 1 ou 2 leituras por sensor. Para testar a lógica, reduza intervalo e janela proporcionalmente por parâmetros.
- **App em segundo plano:** iOS e Android pausam o JavaScript. Mantenha o app aberto e a tela ligada.
- **Erro `ENOSPC` no Metro:** aplique o ajuste de `inotify` da seção 4.4.
- **Race condition no buffer do CAT:** o callback do MQTT roda em outra thread, então proteja o buffer com `Lock`.

---

## 9. Checklist final de entrega

- [ ] `docker compose up -d --build` sobe broker, CAT, Alarms e sensores sem intervenção.
- [ ] Número de sensores simulados ajustável com `--scale`.
- [ ] CAT calcula a média de 120 s e publica `cat/average`.
- [ ] Eventos `sudden_increase` e `high_temperature` publicados corretamente.
- [ ] Alarms exibe os eventos na interface gráfica, com média, sensores online e gráfico.
- [ ] App Expo publica no mesmo broker e aparece como sensor online.
- [ ] README completo e repositório organizado nas pastas `sensors-sim`, `cat-service`, `alarms-service` e `mobile-app`.
