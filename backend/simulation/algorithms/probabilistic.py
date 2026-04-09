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
        open_flowers = self._open_flowers(flowers)
        if not open_flowers:
            return
        loads = self._flower_loads(bees)
        for bee in self._idle_bees(bees, open_flowers):
            weights = []
            for flower in open_flowers:
                load = loads.get(flower.id, 0)
                capacity = self._flower_capacity(flower)
                overload = max(0, load - capacity + 1)
                distance_factor = 1.0 + bee.pos.distance_to(flower.pos) / 45.0
                load_factor = (load + 1) ** 1.6
                overload_factor = (overload + 1) ** 2.0
                weight = (flower.nectar + 0.2) / distance_factor / load_factor / overload_factor
                weights.append(max(0.01, weight))
            chosen = random.choices(open_flowers, weights=weights, k=1)[0]
            self._assign_bee_to_flower(bee, chosen)
            loads[chosen.id] = loads.get(chosen.id, 0) + 1
