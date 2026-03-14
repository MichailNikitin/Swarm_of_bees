"""Agent definitions for the bee swarm simulation."""
from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class BeeState(str, Enum):
    IDLE = "idle"
    TO_FLOWER = "to_flower"
    COLLECTING = "collecting"
    TO_HIVE = "to_hive"
    UNLOADING = "unloading"


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
        return Vec2(self.x + (target.x - self.x) * ratio,
                    self.y + (target.y - self.y) * ratio)


@dataclass
class Bee:
    id: str
    pos: Vec2
    state: BeeState = BeeState.IDLE
    nectar: float = 0.0
    target_flower_id: Optional[str] = None
    max_nectar: float = 1.0
    collect_rate: float = 0.2
    unload_rate: float = 0.5

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": "bee",
            "x": round(self.pos.x, 2),
            "y": round(self.pos.y, 2),
            "state": self.state.value,
            "nectar": round(self.nectar, 3),
            "target_flower_id": self.target_flower_id,
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
    id: str = "hive"
    pos: Vec2 = field(default_factory=lambda: Vec2(0, 0))
    nectar: float = 0.0
    honey: float = 0.0
    nectar_to_honey_ratio: float = 3.0

    def process_nectar(self, amount: float) -> float:
        """Add nectar and convert to honey. Returns honey produced."""
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
            "nectar": round(self.nectar, 3),
            "honey": round(self.honey, 3),
        }


def make_bee(bee_id: str, canvas_w: float, canvas_h: float) -> Bee:
    return Bee(
        id=bee_id,
        pos=Vec2(
            random.uniform(canvas_w * 0.3, canvas_w * 0.7),
            random.uniform(canvas_h * 0.3, canvas_h * 0.7),
        ),
    )


def make_flower(flower_id: str, canvas_w: float, canvas_h: float) -> Flower:
    margin = 60
    return Flower(
        id=flower_id,
        pos=Vec2(
            random.uniform(margin, canvas_w - margin),
            random.uniform(margin, canvas_h - margin),
        ),
        nectar=random.uniform(2.0, 5.0),
    )
