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
        self._assign_balanced(
            bees,
            flowers,
            lambda bee, flower, load, capacity:
                flower.nectar * 10.0 - bee.pos.distance_to(flower.pos) / 10.0,
        )
