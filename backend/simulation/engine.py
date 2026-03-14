"""Core simulation engine — runs async tick loop and updates all agents."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, Optional

from .agents import (
    Bee, BeeState, Flower, FlowerState, Hive, Vec2,
    make_bee, make_flower,
)
from .controller import SwarmController

# Default canvas dimensions used for initial placement
DEFAULT_CANVAS_W = 900
DEFAULT_CANVAS_H = 600
ARRIVAL_THRESHOLD = 8.0  # px — distance to consider "arrived"


@dataclass
class SimParams:
    bee_speed: float = 3.0          # px/tick
    nectar_regen: float = 0.05      # units/tick
    num_bees: int = 10
    num_flowers: int = 5
    tick_rate: float = 10.0         # ticks/sec
    collect_rate: float = 0.2
    unload_rate: float = 0.5
    max_bee_nectar: float = 1.0
    canvas_w: float = DEFAULT_CANVAS_W
    canvas_h: float = DEFAULT_CANVAS_H


@dataclass
class SimulationState:
    bees: Dict[str, Bee] = field(default_factory=dict)
    flowers: Dict[str, Flower] = field(default_factory=dict)
    hive: Hive = field(default_factory=Hive)
    tick_count: int = 0
    total_nectar_collected: float = 0.0


class SimulationEngine:
    def __init__(self) -> None:
        self.params = SimParams()
        self.state = SimulationState()
        self.controller = SwarmController()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._broadcast_callback: Optional[Callable[[dict], Coroutine]] = None
        self._init_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_broadcast_callback(self, cb: Callable[[dict], Coroutine]) -> None:
        self._broadcast_callback = cb

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

    def reset(self, params: Optional[dict] = None) -> None:
        self.stop()
        if params:
            self.update_params(params)
        self.state = SimulationState()
        self._init_state()

    def update_params(self, data: dict) -> None:
        p = self.params
        if "bee_speed" in data:
            p.bee_speed = float(data["bee_speed"])
        if "nectar_regen" in data:
            p.nectar_regen = float(data["nectar_regen"])
            for flower in self.state.flowers.values():
                flower.regen_rate = p.nectar_regen
        if "num_bees" in data:
            self._resize_bees(int(data["num_bees"]))
        if "num_flowers" in data:
            self._resize_flowers(int(data["num_flowers"]))
        if "tick_rate" in data:
            p.tick_rate = max(1.0, min(30.0, float(data["tick_rate"])))
        if "canvas_w" in data:
            p.canvas_w = float(data["canvas_w"])
        if "canvas_h" in data:
            p.canvas_h = float(data["canvas_h"])

    def get_snapshot(self) -> dict:
        s = self.state
        p = self.params
        return {
            "tick": s.tick_count,
            "running": self._running,
            "bees": [b.to_dict() for b in s.bees.values()],
            "flowers": [f.to_dict() for f in s.flowers.values()],
            "hive": s.hive.to_dict(),
            "stats": {
                "total_nectar_collected": round(s.total_nectar_collected, 2),
                "total_honey": round(s.hive.honey, 3),
                "active_bees": sum(
                    1 for b in s.bees.values() if b.state != BeeState.IDLE
                ),
                "open_flowers": sum(
                    1 for f in s.flowers.values() if f.state == FlowerState.OPEN
                ),
            },
            "params": {
                "bee_speed": p.bee_speed,
                "nectar_regen": p.nectar_regen,
                "num_bees": p.num_bees,
                "num_flowers": p.num_flowers,
                "tick_rate": p.tick_rate,
            },
        }

    # ------------------------------------------------------------------
    # Internal init helpers
    # ------------------------------------------------------------------

    def _init_state(self) -> None:
        p = self.params
        hive_pos = Vec2(p.canvas_w / 2, p.canvas_h / 2)
        self.state.hive = Hive(pos=hive_pos)

        for i in range(p.num_bees):
            bee = make_bee(f"bee_{i}", p.canvas_w, p.canvas_h)
            bee.max_nectar = p.max_bee_nectar
            bee.collect_rate = p.collect_rate
            bee.unload_rate = p.unload_rate
            self.state.bees[bee.id] = bee

        for i in range(p.num_flowers):
            flower = make_flower(f"flower_{i}", p.canvas_w, p.canvas_h)
            flower.regen_rate = p.nectar_regen
            self.state.flowers[flower.id] = flower

    def _resize_bees(self, target: int) -> None:
        p = self.params
        current = list(self.state.bees.keys())
        if target > len(current):
            for i in range(len(current), target):
                bee = make_bee(f"bee_{i}", p.canvas_w, p.canvas_h)
                bee.max_nectar = p.max_bee_nectar
                bee.collect_rate = p.collect_rate
                bee.unload_rate = p.unload_rate
                self.state.bees[bee.id] = bee
        elif target < len(current):
            to_remove = current[target:]
            for bid in to_remove:
                del self.state.bees[bid]
        p.num_bees = target

    def _resize_flowers(self, target: int) -> None:
        p = self.params
        current = list(self.state.flowers.keys())
        if target > len(current):
            for i in range(len(current), target):
                flower = make_flower(f"flower_{i}", p.canvas_w, p.canvas_h)
                flower.regen_rate = p.nectar_regen
                self.state.flowers[flower.id] = flower
        elif target < len(current):
            to_remove = current[target:]
            for fid in to_remove:
                del self.state.flowers[fid]
                # Unassign bees targeting removed flower
                for bee in self.state.bees.values():
                    if bee.target_flower_id == fid:
                        bee.target_flower_id = None
                        bee.state = BeeState.IDLE
        p.num_flowers = target

    # ------------------------------------------------------------------
    # Tick loop
    # ------------------------------------------------------------------

    async def _loop(self) -> None:
        while self._running:
            t_start = time.monotonic()
            self._tick()
            if self._broadcast_callback:
                snapshot = self.get_snapshot()
                await self._broadcast_callback(snapshot)
            elapsed = time.monotonic() - t_start
            interval = 1.0 / self.params.tick_rate
            sleep_time = max(0.0, interval - elapsed)
            await asyncio.sleep(sleep_time)

    def _tick(self) -> None:
        self.state.tick_count += 1
        self._update_flowers()
        self._update_bees()
        self.controller.tick(self.state)

    def _update_flowers(self) -> None:
        for flower in self.state.flowers.values():
            flower.regen_rate = self.params.nectar_regen
            if flower.nectar < flower.max_nectar:
                flower.nectar = min(
                    flower.max_nectar, flower.nectar + flower.regen_rate
                )

    def _update_bees(self) -> None:
        hive_pos = self.state.hive.pos
        speed = self.params.bee_speed

        for bee in self.state.bees.values():
            if bee.state == BeeState.IDLE:
                pass  # controller will assign

            elif bee.state == BeeState.TO_FLOWER:
                flower = self.state.flowers.get(bee.target_flower_id or "")
                if flower is None:
                    bee.state = BeeState.IDLE
                    bee.target_flower_id = None
                    continue
                bee.pos = bee.pos.move_toward(flower.pos, speed)
                if bee.pos.distance_to(flower.pos) < ARRIVAL_THRESHOLD:
                    bee.state = BeeState.COLLECTING

            elif bee.state == BeeState.COLLECTING:
                flower = self.state.flowers.get(bee.target_flower_id or "")
                if flower is None or flower.state == FlowerState.CLOSED:
                    bee.state = BeeState.IDLE
                    bee.target_flower_id = None
                    continue
                collect = min(
                    bee.collect_rate,
                    bee.max_nectar - bee.nectar,
                    flower.nectar,
                )
                flower.nectar -= collect
                bee.nectar += collect
                self.state.total_nectar_collected += collect
                if bee.nectar >= bee.max_nectar:
                    bee.state = BeeState.TO_HIVE
                    bee.target_flower_id = None

            elif bee.state == BeeState.TO_HIVE:
                bee.pos = bee.pos.move_toward(hive_pos, speed)
                if bee.pos.distance_to(hive_pos) < ARRIVAL_THRESHOLD:
                    bee.state = BeeState.UNLOADING

            elif bee.state == BeeState.UNLOADING:
                unload = min(bee.unload_rate, bee.nectar)
                bee.nectar -= unload
                self.state.hive.process_nectar(unload)
                if bee.nectar <= 0.0:
                    bee.nectar = 0.0
                    bee.state = BeeState.IDLE
