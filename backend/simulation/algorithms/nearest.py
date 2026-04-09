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
        self._assign_balanced(
            bees,
            flowers,
            lambda bee, flower, load, capacity:
                flower.nectar * 2.0 - bee.pos.distance_to(flower.pos) / 6.0,
        )
