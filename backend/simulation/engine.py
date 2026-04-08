"""Core simulation engine — async tick loop, multi-hive support."""
from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass, field
from typing import Callable, Coroutine, Dict, List, Optional

from .agents import (
    Bee, BeeState, Flower, FlowerState, Hive, HIVE_COLORS, Vec2,
    Obstacle, BEE_RADIUS,
    make_bee, make_flower, make_obstacle,
)
from .algorithms import list_algorithms
from .controller import SwarmController

DEFAULT_CANVAS_W = 900
DEFAULT_CANVAS_H = 600
ARRIVAL_THRESHOLD = 8.0   # px — for flowers
# The hive is drawn much larger than its logical arrival zone on purpose:
# bees should visually fly inside the hive before they start unloading/resting.
HIVE_CORE_ARRIVAL = 10.0   # px — actual arrival radius near the hive center
HIVE_REST_RADIUS = 56.0    # px — bees can rest/recover anywhere inside the hive area
DEFAULT_SEPARATION_DIST = 25.0  # px — default safe zone radius around each bee
OBSTACLE_MARGIN = 8.0     # extra clearance around obstacles

# States where bee is "at the hive" and shouldn't be pushed away by separation
_HIVE_STATES = frozenset({BeeState.RESTING, BeeState.UNLOADING, BeeState.IDLE})


@dataclass
class SimParams:
    bee_speed: float = 3.0
    separation_distance: float = DEFAULT_SEPARATION_DIST
    nectar_regen: float = 0.05
    bees_per_hive: int = 10
    num_flowers: int = 5
    tick_rate: float = 10.0
    collect_rate: float = 0.2
    unload_rate: float = 0.5
    max_bee_nectar: float = 1.0
    canvas_w: float = DEFAULT_CANVAS_W
    canvas_h: float = DEFAULT_CANVAS_H
    # Energy system
    energy_drain_move: float = 0.3
    energy_drain_collect: float = 0.5
    energy_drain_unload: float = 0.2
    energy_drain_carry: float = 0.4
    energy_regen_rate: float = 1.5
    energy_low_threshold: float = 20.0
    num_obstacles: int = 5


@dataclass
class SimulationState:
    bees: Dict[str, Bee] = field(default_factory=dict)
    flowers: Dict[str, Flower] = field(default_factory=dict)
    hives: Dict[str, Hive] = field(default_factory=dict)
    obstacles: Dict[str, Obstacle] = field(default_factory=dict)
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
        self._obstacle_counter = 0
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
        self._obstacle_counter = 0
        self.controller = SwarmController()
        self._init_state()

    def update_params(self, data: dict) -> None:
        self._apply_params(data)

    def add_hive(self, algorithm_name: str = "greedy") -> dict:
        idx = self._hive_counter
        self._hive_counter += 1
        hive_id = f"hive_{idx}"
        color = HIVE_COLORS[idx % len(HIVE_COLORS)]

        # Reposition ALL hives in a circle and shift their bees accordingly
        new_count = len(self.state.hives) + 1
        positions = self._hive_positions(new_count)
        for i, hive in enumerate(self.state.hives.values()):
            old_pos = hive.pos
            hive.pos = positions[i]
            dx = hive.pos.x - old_pos.x
            dy = hive.pos.y - old_pos.y
            for bee in self.state.bees.values():
                if bee.hive_id == hive.id:
                    bee.pos.x += dx
                    bee.pos.y += dy
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
            "obstacles": [o.to_dict() for o in s.obstacles.values()],
            "hives": [h.to_dict() for h in s.hives.values()],
            "stats": {
                "total_nectar_collected": round(s.total_nectar_collected, 2),
                "total_honey": round(total_honey, 3),
                "total_hive_nectar": round(total_hive_nectar, 3),
                "active_bees": sum(1 for b in s.bees.values() if b.state not in (BeeState.IDLE, BeeState.RESTING, BeeState.UNCONSCIOUS)),
                "open_flowers": sum(1 for f in s.flowers.values() if f.state == FlowerState.OPEN),
                "unconscious_bees": sum(1 for b in s.bees.values() if b.state == BeeState.UNCONSCIOUS),
                "resting_bees": sum(1 for b in s.bees.values() if b.state == BeeState.RESTING),
            },
            "params": {
                "bee_speed": p.bee_speed,
                "separation_distance": p.separation_distance,
                "nectar_regen": p.nectar_regen,
                "num_bees": p.bees_per_hive,
                "num_flowers": p.num_flowers,
                "tick_rate": p.tick_rate,
                "num_obstacles": p.num_obstacles,
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
        # Obstacles
        for _ in range(p.num_obstacles):
            oid = f"obs_{self._obstacle_counter}"
            self._obstacle_counter += 1
            obs = make_obstacle(oid, p.canvas_w, p.canvas_h, list(self.state.obstacles.values()))
            self.state.obstacles[oid] = obs

        for _ in range(p.num_flowers):
            fid = f"flower_{self._flower_counter}"
            self._flower_counter += 1
            flower = make_flower(fid, p.canvas_w, p.canvas_h, list(self.state.obstacles.values()))
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
                flower = make_flower(fid, p.canvas_w, p.canvas_h, list(self.state.obstacles.values()))
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
        if "separation_distance" in data:
            p.separation_distance = max(BEE_RADIUS * 2.0, float(data["separation_distance"]))
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
            p.tick_rate = max(1.0, min(90.0, float(data["tick_rate"])))
        if "canvas_w" in data:
            p.canvas_w = float(data["canvas_w"])
        if "canvas_h" in data:
            p.canvas_h = float(data["canvas_h"])
        if "num_obstacles" in data:
            p.num_obstacles = int(data["num_obstacles"])

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

    # ── Steering movement ──────────────────────────────────────────────

    def _bee_near_own_hive(self, bee: Bee) -> bool:
        hive = self.state.hives.get(bee.hive_id)
        return hive is not None and bee.pos.distance_to(hive.pos) < HIVE_REST_RADIUS

    def _steer_move(self, bee: Bee, target: Vec2, speed: float) -> None:
        """Move bee toward target while avoiding obstacles and other bees."""
        p = self.params
        dx = target.x - bee.pos.x
        dy = target.y - bee.pos.y
        dist = math.hypot(dx, dy)
        if dist < 1.0:
            return

        # Desired direction (normalized)
        dir_x = dx / dist
        dir_y = dy / dist

        # Accumulate steering forces
        steer_x, steer_y = dir_x, dir_y

        # --- Obstacle avoidance ---
        for obs in self.state.obstacles.values():
            ox = bee.pos.x - obs.pos.x
            oy = bee.pos.y - obs.pos.y
            odist = math.hypot(ox, oy)
            min_dist = obs.radius + BEE_RADIUS + OBSTACLE_MARGIN
            if odist < min_dist and odist > 0.1:
                # Strong repulsion — scale inversely with distance
                force = (min_dist - odist) / min_dist * 3.0
                steer_x += (ox / odist) * force
                steer_y += (oy / odist) * force

        # --- Bee separation (skip if both bees are resting at their hive) ---
        bee_at_hive = bee.state in _HIVE_STATES and self._bee_near_own_hive(bee)
        separation_dist = p.separation_distance
        for other in self.state.bees.values():
            if other.id == bee.id:
                continue
            # Don't push apart bees that are both hanging out at the hive
            if bee_at_hive and other.state in _HIVE_STATES \
                    and other.hive_id == bee.hive_id:
                continue
            bx = bee.pos.x - other.pos.x
            by = bee.pos.y - other.pos.y
            bdist = math.hypot(bx, by)
            if bdist < separation_dist and bdist > 0.1:
                force = (separation_dist - bdist) / separation_dist * 1.2
                steer_x += (bx / bdist) * force
                steer_y += (by / bdist) * force

        # Normalize and apply speed
        mag = math.hypot(steer_x, steer_y)
        if mag > 0.01:
            steer_x /= mag
            steer_y /= mag

        move_dist = min(speed, dist)
        new_x = bee.pos.x + steer_x * move_dist
        new_y = bee.pos.y + steer_y * move_dist

        # Hard constraint: don't enter obstacles
        for obs in self.state.obstacles.values():
            ox = new_x - obs.pos.x
            oy = new_y - obs.pos.y
            odist = math.hypot(ox, oy)
            min_dist = obs.radius + BEE_RADIUS
            if odist < min_dist and odist > 0.1:
                # Push out to boundary
                new_x = obs.pos.x + (ox / odist) * min_dist
                new_y = obs.pos.y + (oy / odist) * min_dist

        # Clamp to canvas
        new_x = max(BEE_RADIUS, min(p.canvas_w - BEE_RADIUS, new_x))
        new_y = max(BEE_RADIUS, min(p.canvas_h - BEE_RADIUS, new_y))

        bee.pos.x = new_x
        bee.pos.y = new_y

    def _drain_energy(self, bee: Bee, amount: float) -> bool:
        """Drain energy. Returns True if bee stays conscious."""
        bee.energy = max(0.0, bee.energy - amount)
        if bee.energy <= 0.0:
            bee.state = BeeState.UNCONSCIOUS
            bee.target_flower_id = None
            # Drop carry if was carrying
            if bee.carry_target_id:
                target = self.state.bees.get(bee.carry_target_id)
                if target and bee.id in target.carried_by:
                    target.carried_by.remove(bee.id)
                bee.carry_target_id = None
            return False
        return True

    def _validate_carry_refs(self) -> None:
        """Clean up stale carrying references."""
        for bee in self.state.bees.values():
            if bee.carry_target_id:
                target = self.state.bees.get(bee.carry_target_id)
                if not target or target.state != BeeState.UNCONSCIOUS:
                    bee.carry_target_id = None
                    if bee.state == BeeState.CARRYING:
                        bee.state = BeeState.IDLE
            bee.carried_by = [
                cid for cid in bee.carried_by
                if cid in self.state.bees
                and self.state.bees[cid].state == BeeState.CARRYING
                and self.state.bees[cid].carry_target_id == bee.id
            ]

    def _update_bees(self) -> None:
        p = self.params
        speed = p.bee_speed

        self._validate_carry_refs()

        # ── Pass 1: individual bee state machine ──────────────────────
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
                self._steer_move(bee, flower.pos, speed)
                if not self._drain_energy(bee, p.energy_drain_move):
                    continue
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
                if not self._drain_energy(bee, p.energy_drain_collect):
                    continue
                if bee.nectar >= bee.max_nectar:
                    bee.state = BeeState.TO_HIVE
                    bee.target_flower_id = None

            elif bee.state == BeeState.TO_HIVE:
                if hive is None:
                    bee.state = BeeState.IDLE
                    continue
                self._steer_move(bee, hive.pos, speed)
                if not self._drain_energy(bee, p.energy_drain_move):
                    continue
                if bee.pos.distance_to(hive.pos) < HIVE_CORE_ARRIVAL:
                    bee.state = BeeState.UNLOADING

            elif bee.state == BeeState.UNLOADING:
                if hive is None:
                    bee.state = BeeState.IDLE
                    continue
                unload = min(bee.unload_rate, bee.nectar)
                bee.nectar -= unload
                hive.process_nectar(unload)
                if not self._drain_energy(bee, p.energy_drain_unload):
                    continue
                if bee.nectar <= 0.0:
                    bee.nectar = 0.0
                    if bee.energy <= p.energy_low_threshold:
                        bee.state = BeeState.RESTING
                    else:
                        bee.state = BeeState.IDLE

            elif bee.state == BeeState.RETURNING_HOME:
                if hive is None:
                    bee.state = BeeState.IDLE
                    continue
                self._steer_move(bee, hive.pos, speed)
                if not self._drain_energy(bee, p.energy_drain_move):
                    continue
                if bee.pos.distance_to(hive.pos) < HIVE_REST_RADIUS:
                    bee.state = BeeState.RESTING

            elif bee.state == BeeState.RESTING:
                bee.energy = min(bee.max_energy, bee.energy + p.energy_regen_rate)
                if bee.energy >= bee.max_energy:
                    bee.state = BeeState.IDLE

            elif bee.state == BeeState.UNCONSCIOUS:
                pass  # handled by carriers in pass 2

            elif bee.state == BeeState.CARRYING:
                pass  # handled in pass 2

            # Low energy check: proactively return home
            if bee.state in (BeeState.TO_FLOWER, BeeState.COLLECTING) \
                    and bee.energy <= p.energy_low_threshold:
                bee.state = BeeState.RETURNING_HOME
                bee.target_flower_id = None

        # ── Pass 2: carrying coordination ─────────────────────────────
        carry_groups: Dict[str, list] = {}
        for bee in self.state.bees.values():
            if bee.state == BeeState.CARRYING and bee.carry_target_id:
                carry_groups.setdefault(bee.carry_target_id, []).append(bee)

        for target_id, carriers in carry_groups.items():
            target = self.state.bees.get(target_id)
            if not target or target.state != BeeState.UNCONSCIOUS:
                for c in carriers:
                    c.state = BeeState.IDLE
                    c.carry_target_id = None
                continue

            target_hive = self.state.hives.get(target.hive_id)
            if not target_hive:
                continue

            n_carriers = len(carriers)
            eff_speed = speed * (1.0 if n_carriers >= 2 else 0.5)

            # Move carriers toward the unconscious bee first, then toward hive
            arrived_at_target = all(
                c.pos.distance_to(target.pos) < ARRIVAL_THRESHOLD for c in carriers
            )

            if not arrived_at_target:
                # Carriers move toward the unconscious bee
                for c in carriers:
                    self._steer_move(c, target.pos, eff_speed)
                    if not self._drain_energy(c, p.energy_drain_carry):
                        if target and c.id in target.carried_by:
                            target.carried_by.remove(c.id)
            else:
                # All carriers reached the target — move together toward hive
                for c in carriers:
                    self._steer_move(c, target_hive.pos, eff_speed)
                    if not self._drain_energy(c, p.energy_drain_carry):
                        if target and c.id in target.carried_by:
                            target.carried_by.remove(c.id)

                # Move unconscious bee with carriers (average position)
                alive_carriers = [c for c in carriers if c.state == BeeState.CARRYING]
                if alive_carriers:
                    target.pos.x = sum(c.pos.x for c in alive_carriers) / len(alive_carriers)
                    target.pos.y = sum(c.pos.y for c in alive_carriers) / len(alive_carriers)

                # Check arrival at hive
                if target.pos.distance_to(target_hive.pos) < HIVE_REST_RADIUS:
                    target.state = BeeState.RESTING
                    target.carried_by.clear()
                    for c in alive_carriers:
                        c.carry_target_id = None
                        if c.energy <= p.energy_low_threshold:
                            c.state = BeeState.RESTING
                        else:
                            c.state = BeeState.IDLE
