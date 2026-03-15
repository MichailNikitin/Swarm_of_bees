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
        open_flowers = [f for f in flowers.values() if f.state == FlowerState.OPEN]
        if not open_flowers:
            return
        for bee in bees:
            if bee.state != BeeState.IDLE:
                continue
            flower = open_flowers[self._counter % len(open_flowers)]
            bee.target_flower_id = flower.id
            bee.state = BeeState.TO_FLOWER
            self._counter += 1
