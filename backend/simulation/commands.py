"""Command data types for the command-based algorithm system."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass
class BeeCommand:
    """Low-level command issued to a bee by a command-based algorithm."""
    action: str         # "move", "collect", "unload", "rest", "idle", "pickup"
    angle: float = 0.0  # radians, for "move" (0=right, π/2=down)
    speed_factor: float = 1.0   # 0.0-1.0 speed multiplier
    target_id: str = ""         # for "pickup" — id of unconscious bee


CommandDict = Dict[str, BeeCommand]


# ── Read-only view objects (frozen — algorithms cannot mutate state) ──────


@dataclass(frozen=True)
class BeeView:
    id: str
    x: float
    y: float
    energy: float
    max_energy: float
    nectar: float
    max_nectar: float
    state: str
    carry_target_id: Optional[str]
    carried_by: Tuple[str, ...]
    hive_id: str


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


@dataclass(frozen=True)
class WorldView:
    hive_id: str
    hive_x: float
    hive_y: float
    hive_nectar: float
    hive_honey: float
    bees: Tuple[BeeView, ...]           # only this hive's bees
    all_bees: Tuple[BeeView, ...]       # all bees (global knowledge)
    flowers: Tuple[FlowerView, ...]
    obstacles: Tuple[ObstacleView, ...]
    canvas_w: float
    canvas_h: float
    tick: int
