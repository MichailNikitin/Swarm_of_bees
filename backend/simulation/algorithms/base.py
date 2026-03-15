"""Abstract base class for all swarm algorithms."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, List

if TYPE_CHECKING:
    from ..agents import Bee, Flower, Hive

from ..agents import BeeState


class BaseSwarmAlgorithm(ABC):
    """
    Interface every swarm algorithm must implement.

    Each tick the controller calls  tick(hive, bees, flowers)  for every hive.
    The default tick() implementation:
      1. sends full bees back to hive  (shared across all algorithms)
      2. calls assign_idle_bees()      (algorithm-specific)

    Subclasses only need to override assign_idle_bees().
    They may also override tick() completely for more exotic behaviour.

    IMPORTANT: do NOT modify flower.state — that is managed globally by the
    engine._update_flowers() method to avoid race conditions between hives.
    """

    name: str = ""
    description: str = ""

    def tick(
        self,
        hive: "Hive",
        bees: List["Bee"],
        flowers: Dict[str, "Flower"],
    ) -> None:
        self._send_full_bees_to_hive(bees)
        self.assign_idle_bees(bees, flowers)

    @abstractmethod
    def assign_idle_bees(
        self,
        bees: List["Bee"],
        flowers: Dict[str, "Flower"],
    ) -> None:
        """Assign BeeState.IDLE bees to open flowers. Core algorithm logic."""

    # ── Shared helper ─────────────────────────────────────────────────

    def _send_full_bees_to_hive(self, bees: List["Bee"]) -> None:
        for bee in bees:
            if bee.nectar >= bee.max_nectar and bee.state not in (
                BeeState.TO_HIVE,
                BeeState.UNLOADING,
            ):
                bee.state = BeeState.TO_HIVE
                bee.target_flower_id = None
