"""Safety-first algorithm — rescue unconscious bees before collecting nectar."""
from __future__ import annotations

from typing import Dict, List

from .base import BaseSwarmAlgorithm
from .registry import register
from ..agents import Bee, BeeState, Flower, FlowerState


@register
class SafetyAlgorithm(BaseSwarmAlgorithm):
    """
    Безопасный алгоритм.
    Приоритет — спасение бессознательных пчёл. Пчёлы отзываются
    с заданий ради спасения. Оставшиеся свободные пчёлы летят
    к ближайшему цветку.
    """

    name = "safety"
    description = "Безопасный: спасение пчёл в приоритете"

    def tick(
        self,
        hive: "Hive",
        bees: List["Bee"],
        flowers: Dict[str, "Flower"],
    ) -> None:
        self._send_full_bees_to_hive(bees)
        # Recall bees from flower tasks to create free rescuers
        self._recall_for_rescue(bees)
        # Dispatch rescuers (now there should be IDLE bees available)
        self._dispatch_rescuers(bees)
        # Remaining idle bees go collect
        self.assign_idle_bees(bees, flowers)

    def assign_idle_bees(
        self,
        bees: List[Bee],
        flowers: Dict[str, Flower],
    ) -> None:
        self._assign_balanced(
            bees,
            flowers,
            lambda bee, flower, load, capacity:
                flower.nectar * 1.5 - bee.pos.distance_to(flower.pos) / 5.0,
        )
