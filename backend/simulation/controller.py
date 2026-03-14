"""Swarm Intelligence Controller — centralized decision algorithm."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .engine import SimulationState

from .agents import BeeState, FlowerState


class SwarmController:
    """
    Centralized controller that reads full simulation telemetry each tick
    and issues commands to all agents.
    """

    def tick(self, state: "SimulationState") -> None:
        self._update_flower_states(state)
        self._assign_idle_bees(state)
        self._send_full_bees_to_hive(state)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _update_flower_states(self, state: "SimulationState") -> None:
        for flower in state.flowers.values():
            if flower.state == FlowerState.OPEN and flower.nectar < 0.5:
                flower.state = FlowerState.CLOSED
            elif flower.state == FlowerState.CLOSED and flower.nectar > 3.0:
                flower.state = FlowerState.OPEN

    def _assign_idle_bees(self, state: "SimulationState") -> None:
        open_flowers = sorted(
            [f for f in state.flowers.values() if f.state == FlowerState.OPEN],
            key=lambda f: f.nectar,
            reverse=True,
        )
        if not open_flowers:
            return

        assigned: dict[str, int] = {f.id: 0 for f in open_flowers}
        # Count already assigned bees
        for bee in state.bees.values():
            if bee.target_flower_id and bee.target_flower_id in assigned:
                assigned[bee.target_flower_id] += 1

        flower_idx = 0
        for bee in state.bees.values():
            if bee.state != BeeState.IDLE:
                continue
            # Pick flower with most nectar that has fewest assigned bees (round-robin over sorted list)
            best = open_flowers[flower_idx % len(open_flowers)]
            bee.target_flower_id = best.id
            bee.state = BeeState.TO_FLOWER
            assigned[best.id] += 1
            flower_idx += 1

    def _send_full_bees_to_hive(self, state: "SimulationState") -> None:
        for bee in state.bees.values():
            if bee.nectar >= bee.max_nectar and bee.state not in (
                BeeState.TO_HIVE,
                BeeState.UNLOADING,
            ):
                bee.state = BeeState.TO_HIVE
                bee.target_flower_id = None
