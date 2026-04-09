"""Abstract base class for all swarm algorithms."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable, Dict, List

if TYPE_CHECKING:
    from ..agents import Bee, Flower, Hive

from ..agents import BeeState, FlowerState


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
        self._dispatch_rescuers(bees)
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
        _SKIP = (
            BeeState.TO_HIVE, BeeState.UNLOADING,
            BeeState.UNCONSCIOUS, BeeState.RESTING,
            BeeState.CARRYING, BeeState.RETURNING_HOME,
        )
        for bee in bees:
            if bee.nectar >= bee.max_nectar and bee.state not in _SKIP:
                bee.state = BeeState.TO_HIVE
                bee.target_flower_id = None

    def _dispatch_rescuers(self, bees: List["Bee"]) -> None:
        """Assign idle bees to carry unconscious ones back to the hive."""
        unconscious = [
            b for b in bees
            if b.state == BeeState.UNCONSCIOUS and len(b.carried_by) < 2
        ]
        if not unconscious:
            return
        available = [b for b in bees if b.state == BeeState.IDLE]
        if not available:
            return
        unconscious.sort(key=lambda b: len(b.carried_by))
        for unc in unconscious:
            while len(unc.carried_by) < 2 and available:
                carrier = available.pop(0)
                carrier.state = BeeState.CARRYING
                carrier.carry_target_id = unc.id
                unc.carried_by.append(carrier.id)

    def _recall_for_rescue(self, bees: List["Bee"]) -> None:
        """Pull bees off flower duty to rescue unconscious ones (for safety-first algorithms)."""
        unconscious = [
            b for b in bees
            if b.state == BeeState.UNCONSCIOUS and len(b.carried_by) < 2
        ]
        if not unconscious:
            return
        # How many rescuers do we need?
        needed = sum(2 - len(u.carried_by) for u in unconscious)
        # Pull from TO_FLOWER first (haven't started collecting yet), then COLLECTING
        recallable = [
            b for b in bees
            if b.state in (BeeState.TO_FLOWER, BeeState.COLLECTING)
        ]
        for bee in recallable:
            if needed <= 0:
                break
            bee.state = BeeState.IDLE
            bee.target_flower_id = None
            needed -= 1

    def _open_flowers(
        self,
        flowers: Dict[str, "Flower"],
        *,
        min_nectar: float = 0.0,
    ) -> List["Flower"]:
        return [
            f for f in flowers.values()
            if f.state == FlowerState.OPEN and f.nectar >= min_nectar
        ]

    def _flower_loads(self, bees: List["Bee"]) -> Dict[str, int]:
        loads: Dict[str, int] = {}
        for bee in bees:
            if bee.target_flower_id and bee.state in (BeeState.TO_FLOWER, BeeState.COLLECTING):
                loads[bee.target_flower_id] = loads.get(bee.target_flower_id, 0) + 1
        return loads

    def _flower_capacity(self, flower: "Flower") -> int:
        """Estimate how many bees a flower can support without congestion."""
        return max(1, min(4, int(flower.nectar / 1.5) + 1))

    def _idle_bees(self, bees: List["Bee"], open_flowers: List["Flower"]) -> List["Bee"]:
        if not open_flowers:
            return []
        idle = [bee for bee in bees if bee.state == BeeState.IDLE]
        idle.sort(
            key=lambda bee: (
                min(bee.pos.distance_to(f.pos) for f in open_flowers),
                -bee.energy,
                bee.id,
            )
        )
        return idle

    def _assign_bee_to_flower(self, bee: "Bee", flower: "Flower") -> None:
        bee.target_flower_id = flower.id
        bee.state = BeeState.TO_FLOWER

    def _assign_balanced(
        self,
        bees: List["Bee"],
        flowers: Dict[str, "Flower"],
        score_fn: Callable[["Bee", "Flower", int, int], float],
        *,
        min_nectar: float = 0.0,
    ) -> None:
        """
        Shared task allocator that balances nectar value, distance, and flower load.

        Concrete algorithms provide a score_fn for their own preference profile,
        while this helper prevents too many bees from piling onto the same flower.
        """
        open_flowers = self._open_flowers(flowers, min_nectar=min_nectar)
        if not open_flowers:
            return

        loads = self._flower_loads(bees)
        for bee in self._idle_bees(bees, open_flowers):
            best_flower = None
            best_score = float("-inf")

            for flower in open_flowers:
                load = loads.get(flower.id, 0)
                capacity = self._flower_capacity(flower)
                overload = max(0, load - capacity + 1)
                congestion_penalty = (load / capacity) * 2.0 + overload * 4.0
                score = score_fn(bee, flower, load, capacity) - congestion_penalty
                if score > best_score:
                    best_score = score
                    best_flower = flower

            if best_flower is None:
                continue

            self._assign_bee_to_flower(bee, best_flower)
            loads[best_flower.id] = loads.get(best_flower.id, 0) + 1
