"""Agent definitions for the bee swarm simulation."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

# Palette assigned to hives in order; cycles if more than 8 hives
HIVE_COLORS = [
    "#f5c518",  # жёлтый  (hive_0)
    "#e74c3c",  # красный (hive_1)
    "#3498db",  # синий   (hive_2)
    "#9b59b6",  # фиолетовый
    "#1abc9c",  # бирюзовый
    "#e67e22",  # оранжевый
    "#2ecc71",  # зелёный
    "#e91e63",  # розовый
]


class BeeState(str, Enum):
    IDLE = "idle"
    TO_FLOWER = "to_flower"
    COLLECTING = "collecting"
    TO_HIVE = "to_hive"
    UNLOADING = "unloading"
    RETURNING_HOME = "returning_home"
    RESTING = "resting"
    UNCONSCIOUS = "unconscious"
    CARRYING = "carrying"


class FlowerState(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


@dataclass
class Vec2:
    x: float
    y: float

    def distance_to(self, other: "Vec2") -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def move_toward(self, target: "Vec2", speed: float) -> "Vec2":
        dist = self.distance_to(target)
        if dist <= speed:
            return Vec2(target.x, target.y)
        ratio = speed / dist
        return Vec2(
            self.x + (target.x - self.x) * ratio,
            self.y + (target.y - self.y) * ratio,
        )


@dataclass
class Bee:
    id: str
    pos: Vec2
    hive_id: str = "hive_0"
    color: str = "#f5c518"
    state: BeeState = BeeState.IDLE
    nectar: float = 0.0
    target_flower_id: Optional[str] = None
    max_nectar: float = 1.0
    collect_rate: float = 0.2
    unload_rate: float = 0.5
    energy: float = 100.0
    max_energy: float = 100.0
    carry_target_id: Optional[str] = None
    carried_by: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": "bee",
            "x": round(self.pos.x, 2),
            "y": round(self.pos.y, 2),
            "state": self.state.value,
            "nectar": round(self.nectar, 3),
            "target_flower_id": self.target_flower_id,
            "hive_id": self.hive_id,
            "color": self.color,
            "energy": round(self.energy, 1),
            "max_energy": self.max_energy,
            "carry_target_id": self.carry_target_id,
            "carried_by": list(self.carried_by),
        }


@dataclass
class Flower:
    id: str
    pos: Vec2
    nectar: float = 5.0
    max_nectar: float = 5.0
    state: FlowerState = FlowerState.OPEN
    regen_rate: float = 0.05

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": "flower",
            "x": round(self.pos.x, 2),
            "y": round(self.pos.y, 2),
            "state": self.state.value,
            "nectar": round(self.nectar, 3),
            "max_nectar": self.max_nectar,
        }


@dataclass
class Hive:
    id: str = "hive_0"
    pos: Vec2 = field(default_factory=lambda: Vec2(0, 0))
    algorithm_name: str = "greedy"
    color: str = "#f5c518"
    nectar: float = 0.0
    honey: float = 0.0
    nectar_to_honey_ratio: float = 3.0

    def process_nectar(self, amount: float) -> float:
        """Add raw nectar and convert surplus to honey (3:1). Returns honey produced."""
        self.nectar += amount
        honey_produced = 0.0
        while self.nectar >= self.nectar_to_honey_ratio:
            self.nectar -= self.nectar_to_honey_ratio
            self.honey += 1.0
            honey_produced += 1.0
        return honey_produced

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": "hive",
            "x": round(self.pos.x, 2),
            "y": round(self.pos.y, 2),
            "algorithm_name": self.algorithm_name,
            "color": self.color,
            "nectar": round(self.nectar, 3),
            "honey": round(self.honey, 3),
        }


def make_bee(
    bee_id: str,
    canvas_w: float,
    canvas_h: float,
    hive_id: str = "hive_0",
    color: str = "#f5c518",
    hive_pos: Optional[Vec2] = None,
) -> Bee:
    if hive_pos is not None:
        scatter = 45.0
        x = max(10.0, min(canvas_w - 10.0, hive_pos.x + random.uniform(-scatter, scatter)))
        y = max(10.0, min(canvas_h - 10.0, hive_pos.y + random.uniform(-scatter, scatter)))
    else:
        x = random.uniform(canvas_w * 0.3, canvas_w * 0.7)
        y = random.uniform(canvas_h * 0.3, canvas_h * 0.7)
    return Bee(id=bee_id, pos=Vec2(x, y), hive_id=hive_id, color=color)


BEE_RADIUS = 7.0  # physical radius for collision detection


class ObstacleKind(str, Enum):
    TREE = "tree"
    ROCK = "rock"
    BUSH = "bush"


@dataclass
class Obstacle:
    id: str
    pos: Vec2
    radius: float = 30.0
    kind: ObstacleKind = ObstacleKind.TREE

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "x": round(self.pos.x, 2),
            "y": round(self.pos.y, 2),
            "radius": self.radius,
            "kind": self.kind.value,
        }


def make_obstacle(obs_id: str, canvas_w: float, canvas_h: float, existing: list) -> Obstacle:
    """Create an obstacle at a random position that doesn't overlap existing ones."""
    kind = random.choice(list(ObstacleKind))
    radius = {"tree": 35.0, "rock": 25.0, "bush": 20.0}[kind.value]
    margin = 80  # keep away from edges
    for _ in range(50):  # retry to avoid overlap
        pos = Vec2(
            random.uniform(margin, canvas_w - margin),
            random.uniform(margin, canvas_h - margin),
        )
        # Don't place too close to center (hive area)
        cx, cy = canvas_w / 2, canvas_h / 2
        if math.hypot(pos.x - cx, pos.y - cy) < 100:
            continue
        ok = True
        for other in existing:
            if pos.distance_to(other.pos) < (radius + other.radius + 30):
                ok = False
                break
        if ok:
            return Obstacle(id=obs_id, pos=pos, radius=radius, kind=kind)
    # Fallback — place anyway
    return Obstacle(id=obs_id, pos=pos, radius=radius, kind=kind)


def make_flower(
    flower_id: str, canvas_w: float, canvas_h: float,
    obstacles: Optional[list] = None,
) -> Flower:
    margin = 60
    for _ in range(30):
        pos = Vec2(
            random.uniform(margin, canvas_w - margin),
            random.uniform(margin, canvas_h - margin),
        )
        if obstacles:
            ok = all(
                pos.distance_to(o.pos) > o.radius + 20
                for o in obstacles
            )
            if not ok:
                continue
        return Flower(id=flower_id, pos=pos, nectar=random.uniform(2.0, 5.0))
    # Fallback
    return Flower(id=flower_id, pos=pos, nectar=random.uniform(2.0, 5.0))
