"""Round-robin algorithm — distributes bees evenly across open flowers."""
from __future__ import annotations

from typing import Dict, List

from .base import BaseSwarmAlgorithm
from .registry import register
from ..agents import Bee, BeeState, Flower, FlowerState


@register
class RoundRobinAlgorithm(BaseSwarmAlgorithm):
    """
    Равномерный (Round-Robin).
    Пчёлы по очереди направляются к цветкам из списка открытых.
    Даёт максимально равномерную нагрузку на цветки.
    """

    name = "round_robin"
    description = "Равномерный: поочерёдно по всем открытым цветкам"

    def __init__(self) -> None:
        self._counter: int = 0

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
            ordered = [
                open_flowers[(self._counter + i) % len(open_flowers)]
                for i in range(len(open_flowers))
            ]
            chosen = min(
                ordered,
                key=lambda flower: (
                    max(0, loads.get(flower.id, 0) - self._flower_capacity(flower) + 1),
                    loads.get(flower.id, 0),
                    bee.pos.distance_to(flower.pos),
                ),
            )
            self._assign_bee_to_flower(bee, chosen)
            loads[chosen.id] = loads.get(chosen.id, 0) + 1
            self._counter = (self._counter + 1) % len(open_flowers)
