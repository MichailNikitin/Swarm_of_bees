"""FastAPI server — WebSocket endpoint + static frontend serving."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from simulation.engine import SimulationEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

app = FastAPI(title="Симулятор роя пчёл")
engine = SimulationEngine()

# ── Connected clients ─────────────────────────────────────────────────
clients: Set[WebSocket] = set()


async def broadcast(data: dict) -> None:
    if not clients:
        return
    msg = json.dumps(data)
    dead: Set[WebSocket] = set()
    for ws in clients:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    clients.difference_update(dead)


engine.set_broadcast_callback(broadcast)

# ── Static files ──────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(str(FRONTEND_DIR / "index.html"))


# ── WebSocket ─────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    clients.add(websocket)
    logger.info("Клиент подключился. Всего: %d", len(clients))

    # Отправляем полный снимок сразу (включает algorithms[])
    await websocket.send_text(json.dumps(engine.get_snapshot()))

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            action = msg.get("action")

            if action == "start":
                engine.start()
                await websocket.send_text(json.dumps({"event": "started"}))

            elif action == "stop":
                engine.stop()
                await websocket.send_text(
                    json.dumps({"event": "stopped", **engine.get_snapshot()})
                )

            elif action == "reset":
                engine.reset(msg.get("params"))
                await websocket.send_text(
                    json.dumps({"event": "reset", **engine.get_snapshot()})
                )

            elif action == "update_params":
                engine.update_params(msg.get("params", {}))
                await websocket.send_text(
                    json.dumps({
                        "event": "params_updated",
                        "params": engine.get_snapshot()["params"],
                    })
                )

            # ── Управление ульями ──────────────────────────────────

            elif action == "add_hive":
                algo = msg.get("algorithm_name", "greedy")
                engine.add_hive(algo)
                await websocket.send_text(
                    json.dumps({"event": "hive_added", **engine.get_snapshot()})
                )

            elif action == "remove_hive":
                engine.remove_hive(msg.get("hive_id", ""))
                await websocket.send_text(
                    json.dumps({"event": "hive_removed", **engine.get_snapshot()})
                )

            elif action == "set_hive_algorithm":
                engine.set_hive_algorithm(
                    msg.get("hive_id", ""),
                    msg.get("algorithm_name", "greedy"),
                )
                await websocket.send_text(
                    json.dumps({"event": "algorithm_changed", **engine.get_snapshot()})
                )

            elif action == "get_algorithms":
                await websocket.send_text(
                    json.dumps({
                        "event": "algorithms",
                        "algorithms": engine.get_algorithms(),
                    })
                )

            elif action == "get_snapshot":
                await websocket.send_text(json.dumps(engine.get_snapshot()))

    except WebSocketDisconnect:
        clients.discard(websocket)
        logger.info("Клиент отключился. Всего: %d", len(clients))
    except Exception as exc:
        clients.discard(websocket)
        logger.error("Ошибка WebSocket: %s", exc)
