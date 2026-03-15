"""Core simulation engine — async tick loop, multi-hive support."""
from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass, field
from typing import Callable, Coroutine, Dict, List, Optional

from .agents import (
    Bee, BeeState, Flower, FlowerState, Hive, HIVE_COLORS, Vec2,
    make_bee, make_flower,
)
from .algorithms import list_algorithms
from .controller import SwarmController

DEFAULT_CANVAS_W = 900
DEFAULT_CANVAS_H = 600
ARRIVAL_THRESHOLD = 8.0  # px


@dataclass
class SimParams:
    bee_speed: float = 3.0
    nectar_regen: float = 0.05
    bees_per_hive: int = 10
    num_flowers: int = 5
    tick_rate: float = 10.0
    collect_rate: float = 0.2
    unload_rate: float = 0.5
    max_bee_nectar: float = 1.0
    canvas_w: float = DEFAULT_CANVAS_W
    canvas_h: float = DEFAULT_CANVAS_H


@dataclass
class SimulationState:
    bees: Dict[str, Bee] = field(default_factory=dict)
    flowers: Dict[str, Flower] = field(default_factory=dict)
    hives: Dict[str, Hive] = field(default_factory=dict)
    tick_count: int = 0
    total_nectar_collected: float = 0.0


class SimulationEngine:
    def __init__(self) -> None:
        self.params = SimParams()
        self.state = SimulationState()
        self.controller = SwarmController()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._broadcast: Optional[Callable[[dict], Coroutine]] = None
        self._hive_counter = 0
        self._flower_counter = 0
        self._init_state()

    # ── Public API ────────────────────────────────────────────────────

    def set_broadcast_callback(self, cb: Callable[[dict], Coroutine]) -> None:
        self._broadcast = cb

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
            self._apply_params(params)
        self.state = SimulationState()
        self._hive_counter = 0
        self._flower_counter = 0
        self.controller = SwarmController()
        self._init_state()

    def update_params(self, data: dict) -> None:
        self._apply_params(data)

    def add_hive(self, algorithm_name: str = "greedy") -> dict:
        idx = self._hive_counter
        self._hive_counter += 1
        hive_id = f"hive_{idx}"
        color = HIVE_COLORS[idx % len(HIVE_COLORS)]

        # Reposition ALL hives in a circle
        new_count = len(self.state.hives) + 1
        positions = self._hive_positions(new_count)
        for i, hive in enumerate(self.state.hives.values()):
            hive.pos = positions[i]
        new_pos = positions[-1]

        hive = Hive(id=hive_id, pos=new_pos, algorithm_name=algorithm_name, color=color)
        self.state.hives[hive_id] = hive
        self._create_hive_bees(hive_id, self.params.bees_per_hive, color, new_pos)
        return hive.to_dict()

    def remove_hive(self, hive_id: str) -> None:
        if hive_id not in self.state.hives or len(self.state.hives) <= 1:
            return
        del self.state.hives[hive_id]
        for bid in [b for b, bee in self.state.bees.items() if bee.hive_id == hive_id]:
            del self.state.bees[bid]
        self.controller.invalidate(hive_id)
        # Reposition remaining hives
        positions = self._hive_positions(len(self.state.hives))
        for i, hive in enumerate(self.state.hives.values()):
            hive.pos = positions[i]

    def set_hive_algorithm(self, hive_id: str, algorithm_name: str) -> None:
        if hive_id in self.state.hives:
            self.state.hives[hive_id].algorithm_name = algorithm_name
            # controller._get_instance detects name change and recreates instance

    def get_algorithms(self) -> List[dict]:
        return list_algorithms()

    def get_snapshot(self) -> dict:
        s = self.state
        p = self.params
        total_honey = sum(h.honey for h in s.hives.values())
        total_hive_nectar = sum(h.nectar for h in s.hives.values())
        return {
            "tick": s.tick_count,
            "running": self._running,
            "bees": [b.to_dict() for b in s.bees.values()],
            "flowers": [f.to_dict() for f in s.flowers.values()],
            "hives": [h.to_dict() for h in s.hives.values()],
            "stats": {
                "total_nectar_collected": round(s.total_nectar_collected, 2),
                "total_honey": round(total_honey, 3),
                "total_hive_nectar": round(total_hive_nectar, 3),
                "active_bees": sum(1 for b in s.bees.values() if b.state != BeeState.IDLE),
                "open_flowers": sum(1 for f in s.flowers.values() if f.state == FlowerState.OPEN),
            },
            "params": {
                "bee_speed": p.bee_speed,
                "nectar_regen": p.nectar_regen,
                "num_bees": p.bees_per_hive,
                "num_flowers": p.num_flowers,
                "tick_rate": p.tick_rate,
            },
            "algorithms": list_algorithms(),
        }

    # ── Init helpers ──────────────────────────────────────────────────

    def _init_state(self) -> None:
        p = self.params
        idx = self._hive_counter
        self._hive_counter += 1
        hive_id = f"hive_{idx}"
        color = HIVE_COLORS[idx % len(HIVE_COLORS)]
        hive_pos = Vec2(p.canvas_w / 2, p.canvas_h / 2)
        hive = Hive(id=hive_id, pos=hive_pos, algorithm_name="greedy", color=color)
        self.state.hives[hive_id] = hive
        self._create_hive_bees(hive_id, p.bees_per_hive, color, hive_pos)
        for _ in range(p.num_flowers):
            fid = f"flower_{self._flower_counter}"
            self._flower_counter += 1
            flower = make_flower(fid, p.canvas_w, p.canvas_h)
            flower.regen_rate = p.nectar_regen
            self.state.flowers[fid] = flower

    def _create_hive_bees(
        self, hive_id: str, count: int, color: str, hive_pos: Vec2
    ) -> None:
        p = self.params
        existing = sum(1 for b in self.state.bees.values() if b.hive_id == hive_id)
        for i in range(existing, existing + count):
            bee_id = f"{hive_id}_bee_{i}"
            while bee_id in self.state.bees:
                i += 1
                bee_id = f"{hive_id}_bee_{i}"
            bee = make_bee(bee_id, p.canvas_w, p.canvas_h, hive_id, color, hive_pos)
            bee.max_nectar = p.max_bee_nectar
            bee.collect_rate = p.collect_rate
            bee.unload_rate = p.unload_rate
            self.state.bees[bee_id] = bee

    def _hive_positions(self, n: int) -> List[Vec2]:
        p = self.params
        cx, cy = p.canvas_w / 2, p.canvas_h / 2
        if n == 1:
            return [Vec2(cx, cy)]
        radius = min(p.canvas_w, p.canvas_h) * 0.28
        return [
            Vec2(
                cx + radius * math.cos(2 * math.pi * i / n - math.pi / 2),
                cy + radius * math.sin(2 * math.pi * i / n - math.pi / 2),
            )
            for i in range(n)
        ]

    def _resize_hive_bees(self, hive_id: str, target: int) -> None:
        hive = self.state.hives.get(hive_id)
        if not hive:
            return
        current = [bid for bid, b in self.state.bees.items() if b.hive_id == hive_id]
        diff = target - len(current)
        if diff > 0:
            self._create_hive_bees(hive_id, diff, hive.color, hive.pos)
        elif diff < 0:
            for bid in current[target:]:
                del self.state.bees[bid]

    def _resize_flowers(self, target: int) -> None:
        p = self.params
        current = list(self.state.flowers.keys())
        diff = target - len(current)
        if diff > 0:
            for _ in range(diff):
                fid = f"flower_{self._flower_counter}"
                self._flower_counter += 1
                flower = make_flower(fid, p.canvas_w, p.canvas_h)
                flower.regen_rate = p.nectar_regen
                self.state.flowers[fid] = flower
        elif diff < 0:
            for fid in current[target:]:
                del self.state.flowers[fid]
                for bee in self.state.bees.values():
                    if bee.target_flower_id == fid:
                        bee.target_flower_id = None
                        bee.state = BeeState.IDLE
        p.num_flowers = target

    def _apply_params(self, data: dict) -> None:
        p = self.params
        if "bee_speed" in data:
            p.bee_speed = float(data["bee_speed"])
        if "nectar_regen" in data:
            p.nectar_regen = float(data["nectar_regen"])
            for flower in self.state.flowers.values():
                flower.regen_rate = p.nectar_regen
        if "num_bees" in data or "bees_per_hive" in data:
            target = int(data.get("num_bees", data.get("bees_per_hive", p.bees_per_hive)))
            p.bees_per_hive = target
            for hive_id in list(self.state.hives.keys()):
                self._resize_hive_bees(hive_id, target)
        if "num_flowers" in data:
            self._resize_flowers(int(data["num_flowers"]))
        if "tick_rate" in data:
            p.tick_rate = max(1.0, min(30.0, float(data["tick_rate"])))
        if "canvas_w" in data:
            p.canvas_w = float(data["canvas_w"])
        if "canvas_h" in data:
            p.canvas_h = float(data["canvas_h"])

    # ── Tick loop ─────────────────────────────────────────────────────

    async def _loop(self) -> None:
        while self._running:
            t0 = time.monotonic()
            self._tick()
            if self._broadcast:
                await self._broadcast(self.get_snapshot())
            elapsed = time.monotonic() - t0
            await asyncio.sleep(max(0.0, 1.0 / self.params.tick_rate - elapsed))

    def _tick(self) -> None:
        self.state.tick_count += 1
        self._update_flowers()
        self._update_bees()
        self.controller.tick(self.state)

    def _update_flowers(self) -> None:
        for flower in self.state.flowers.values():
            flower.regen_rate = self.params.nectar_regen
            if flower.nectar < flower.max_nectar:
                flower.nectar = min(flower.max_nectar, flower.nectar + flower.regen_rate)
            # Global state transitions — shared between all hive algorithms
            if flower.state == FlowerState.OPEN and flower.nectar < 0.5:
                flower.state = FlowerState.CLOSED
            elif flower.state == FlowerState.CLOSED and flower.nectar > 3.0:
                flower.state = FlowerState.OPEN

    def _update_bees(self) -> None:
        speed = self.params.bee_speed
        for bee in self.state.bees.values():
            hive = self.state.hives.get(bee.hive_id)

            if bee.state == BeeState.IDLE:
                pass  # algorithm will assign

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
                collect = min(bee.collect_rate, bee.max_nectar - bee.nectar, flower.nectar)
                flower.nectar -= collect
                bee.nectar += collect
                self.state.total_nectar_collected += collect
                if bee.nectar >= bee.max_nectar:
                    bee.state = BeeState.TO_HIVE
                    bee.target_flower_id = None

            elif bee.state == BeeState.TO_HIVE:
                if hive is None:
                    bee.state = BeeState.IDLE
                    continue
                bee.pos = bee.pos.move_toward(hive.pos, speed)
                if bee.pos.distance_to(hive.pos) < ARRIVAL_THRESHOLD:
                    bee.state = BeeState.UNLOADING

            elif bee.state == BeeState.UNLOADING:
                if hive is None:
                    bee.state = BeeState.IDLE
                    continue
                unload = min(bee.unload_rate, bee.nectar)
                bee.nectar -= unload
                hive.process_nectar(unload)
                if bee.nectar <= 0.0:
                    bee.nectar = 0.0
                    bee.state = BeeState.IDLE
