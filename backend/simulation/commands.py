"""Command-based control types for read-only world access."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class BeeCommand:
    action: str
    angle: float = 0.0
    speed_factor: float = 1.0
    target_id: str = ""


@dataclass(frozen=True)
class BeeView:
    id: str
    x: float
    y: float
    hive_id: str
    state: str
    nectar: float
    energy: float
    max_energy: float
    target_flower_id: str | None
    carry_target_id: str | None
    carried_by: Tuple[str, ...]


@dataclass(frozen=True)
class FlowerView:
    id: str
    x: float
    y: float
    nectar: float
    max_nectar: float
    state: str


@dataclass(frozen=True)
class ObstacleView:
    id: str
    x: float
    y: float
    radius: float
    kind: str


@dataclass(frozen=True)
class WorldView:
    hive_id: str
    hive_x: float
    hive_y: float
    hive_nectar: float
    hive_honey: float
    bees: Tuple[BeeView, ...]
    all_bees: Tuple[BeeView, ...]
    flowers: Tuple[FlowerView, ...]
    obstacles: Tuple[ObstacleView, ...]
    canvas_w: float
    canvas_h: float
    tick: int


CommandDict = Dict[str, BeeCommand]
