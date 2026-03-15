"""Probabilistic algorithm — bees choose flowers weighted by nectar level."""
from __future__ import annotations

import random
from typing import Dict, List

from .base import BaseSwarmAlgorithm
from .registry import register
from ..agents import Bee, BeeState, Flower, FlowerState


@register
class ProbabilisticAlgorithm(BaseSwarmAlgorithm):
    """
    Вероятностный алгоритм.
    Пчела выбирает цветок случайно, но вероятность пропорциональна
    количеству нектара: богатые цветки привлекают больше пчёл,
    но не монополизируются как в жадном алгоритме.
    """

    name = "probabilistic"
    description = "Вероятностный: выбор цветка пропорционально нектару"

    def assign_idle_bees(
        self,
        bees: List[Bee],
        flowers: Dict[str, Flower],
    ) -> None:
        open_flowers = [f for f in flowers.values() if f.state == FlowerState.OPEN]
        if not open_flowers:
            return
        # Weight = nectar + small epsilon to keep all flowers reachable
        weights = [f.nectar + 0.1 for f in open_flowers]
        for bee in bees:
            if bee.state != BeeState.IDLE:
                continue
            chosen = random.choices(open_flowers, weights=weights, k=1)[0]
            bee.target_flower_id = chosen.id
            bee.state = BeeState.TO_FLOWER
