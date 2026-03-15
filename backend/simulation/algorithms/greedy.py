"""Greedy algorithm — bees rush to the flower with the most nectar."""
from __future__ import annotations

from typing import Dict, List

from .base import BaseSwarmAlgorithm
from .registry import register
from ..agents import Bee, BeeState, Flower, FlowerState


@register
class GreedyAlgorithm(BaseSwarmAlgorithm):
    """
    Жадный алгоритм.
    Каждая свободная пчела летит к открытому цветку с наибольшим запасом нектара.
    Несколько пчёл могут быть направлены к одному цветку (циклически).
    """

    name = "greedy"
    description = "Жадный: к цветку с максимальным нектаром"

    def assign_idle_bees(
        self,
        bees: List[Bee],
        flowers: Dict[str, Flower],
    ) -> None:
        open_flowers = sorted(
            [f for f in flowers.values() if f.state == FlowerState.OPEN],
            key=lambda f: f.nectar,
            reverse=True,
        )
        if not open_flowers:
            return
        idx = 0
        for bee in bees:
            if bee.state != BeeState.IDLE:
                continue
            bee.target_flower_id = open_flowers[idx % len(open_flowers)].id
            bee.state = BeeState.TO_FLOWER
            idx += 1
