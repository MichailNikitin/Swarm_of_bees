"""Nearest algorithm — each bee flies to the closest open flower."""
from __future__ import annotations

from typing import Dict, List

from .base import BaseSwarmAlgorithm
from .registry import register
from ..agents import Bee, BeeState, Flower, FlowerState


@register
class NearestAlgorithm(BaseSwarmAlgorithm):
    """
    Ближайший цветок.
    Каждая свободная пчела независимо выбирает ближайший открытый цветок.
    Хорошо работает при равномерном распределении цветков.
    """

    name = "nearest"
    description = "Ближайший: лететь к ближайшему открытому цветку"

    def assign_idle_bees(
        self,
        bees: List[Bee],
        flowers: Dict[str, Flower],
    ) -> None:
        open_flowers = [f for f in flowers.values() if f.state == FlowerState.OPEN]
        if not open_flowers:
            return
        for bee in bees:
            if bee.state != BeeState.IDLE:
                continue
            nearest = min(open_flowers, key=lambda f: bee.pos.distance_to(f.pos))
            bee.target_flower_id = nearest.id
            bee.state = BeeState.TO_FLOWER
