import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse

import mqtt_client
from state import AlarmsState

STATIC_DIR = Path(__file__).parent / "static"
KEEPALIVE_S = 15

state = AlarmsState(
    high_threshold=float(os.environ.get("CAT_HIGH_THRESHOLD", "200")),
    max_alarms=int(os.environ.get("ALARMS_MAX", "50")),
    max_history=int(os.environ.get("ALARMS_HISTORY", "200")),
)
state.subscribe(mqtt_client.console_listener)


@asynccontextmanager
async def lifespan(app):
    client = mqtt_client.create_client(state)
    mqtt_client.start(client)
    yield
    mqtt_client.stop(client)


app = FastAPI(lifespan=lifespan)


def sse(kind, data):
    return f"event: {kind}\ndata: {json.dumps(data)}\n\n"


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/state")
def get_state():
    return state.snapshot()


@app.post("/api/alarms/clear")
def clear_alarms():
    state.clear_alarms()
    return {"ok": True}


@app.get("/api/stream")
async def stream():
    loop = asyncio.get_running_loop()
    queue = asyncio.Queue(maxsize=200)

    def put(change):
        try:
            queue.put_nowait(change)
        except asyncio.QueueFull:
            pass

    # Chamado da thread MQTT: só agenda a entrega na fila do event loop.
    def listener(change):
        loop.call_soon_threadsafe(put, change)

    async def events():
        snapshot = state.subscribe(listener)
        try:
            yield sse("state", snapshot)
            while True:
                try:
                    change = await asyncio.wait_for(queue.get(), KEEPALIVE_S)
                    yield sse(change["kind"], change["data"])
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            state.unsubscribe(listener)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
