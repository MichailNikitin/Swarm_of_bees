"""Swarm Intelligence Controller — dispatches per-hive algorithms each tick."""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Set

if TYPE_CHECKING:
    from .engine import SimParams, SimulationState

from .agents import Bee, BeeState, Flower, Hive, Obstacle
from .commands import BeeCommand, BeeView, CommandDict, FlowerView, ObstacleView, WorldView
from .algorithms import get_algorithm
from .algorithms.base import BaseSwarmAlgorithm


class SwarmController:
    """
    Центральный диспетчер: группирует пчёл по ульям, затем
    вызывает алгоритм каждого улья.

    Алгоритмы кешируются, чтобы сохранять внутреннее состояние
    между тиками (важно для алгоритмов с памятью, например ACO).
    При смене алгоритма — старый экземпляр удаляется, создаётся новый.
    """

    def __init__(self) -> None:
        # "{hive_id}:{algo_name}" → algorithm instance
        self._cache: Dict[str, BaseSwarmAlgorithm] = {}
        self.pending_commands: Dict[str, CommandDict] = {}
        self.command_hive_ids: Set[str] = set()
        self.hive_errors: Dict[str, str | None] = {}
        self.hive_debugs: Dict[str, list[str]] = {}

    def refresh_command_hives(self, state: "SimulationState") -> None:
        self.command_hive_ids = set()
        self.hive_errors = {
            hive_id: self.hive_errors.get(hive_id)
            for hive_id in state.hives
        }
        self.hive_debugs = {
            hive_id: self.hive_debugs.get(hive_id, [])
            for hive_id in state.hives
        }
        for hive_id, hive in state.hives.items():
            algo = self._get_instance(hive_id, hive.algorithm_name, state)
            if getattr(algo, "is_command_based", False):
                self.command_hive_ids.add(hive_id)

    def tick(self, state: "SimulationState", params: "SimParams") -> None:
        # Группируем пчёл по ульям
        hive_bees: Dict[str, List[Bee]] = {hid: [] for hid in state.hives}
        for bee in state.bees.values():
            if bee.hive_id in hive_bees:
                hive_bees[bee.hive_id].append(bee)

        self.pending_commands.clear()
        self.refresh_command_hives(state)

        # Запускаем алгоритм для каждого улья
        for hive_id, hive in state.hives.items():
            algo = self._get_instance(hive_id, hive.algorithm_name, state)
            if getattr(algo, "is_command_based", False):
                view = self._build_world_view(hive, hive_bees.get(hive_id, []), state, params)
                commands = algo.compute_commands(view)
                error = getattr(algo, "last_error", None)
                if error:
                    commands = {
                        bee.id: BeeCommand(action="idle")
                        for bee in hive_bees.get(hive_id, [])
                    }
                self.pending_commands[hive_id] = commands
                self.hive_errors[hive_id] = error
                self.hive_debugs[hive_id] = list(getattr(algo, "last_debug", []))
            else:
                self.hive_errors[hive_id] = None
                self.hive_debugs[hive_id] = []
                algo.tick(hive, hive_bees.get(hive_id, []), state.flowers)

    def invalidate(self, hive_id: str) -> None:
        """Вызывается при удалении улья — освобождает кешированный экземпляр."""
        for k in [k for k in self._cache if k.startswith(f"{hive_id}:")]:
            del self._cache[k]
        self.pending_commands.pop(hive_id, None)
        self.command_hive_ids.discard(hive_id)
        self.hive_errors.pop(hive_id, None)
        self.hive_debugs.pop(hive_id, None)

    def get_hive_error(self, hive_id: str) -> str | None:
        return self.hive_errors.get(hive_id)

    def get_hive_debug(self, hive_id: str) -> list[str]:
        return list(self.hive_debugs.get(hive_id, []))

    def _get_instance(
        self,
        hive_id: str,
        algo_name: str,
        state: "SimulationState",
    ) -> BaseSwarmAlgorithm:
        key = f"{hive_id}:{algo_name}"
        if key not in self._cache:
            old_keys = [k for k in self._cache if k.startswith(f"{hive_id}:")]
            old_instances = [self._cache[k] for k in old_keys]
            for k in old_keys:
                del self._cache[k]
            new_instance = get_algorithm(algo_name)
            if old_instances and any(
                getattr(inst, "is_command_based", False) != getattr(new_instance, "is_command_based", False)
                for inst in old_instances
            ):
                self._reset_hive_for_mode_switch(hive_id, state)
            self._cache[key] = new_instance
        return self._cache[key]

    def _reset_hive_for_mode_switch(self, hive_id: str, state: "SimulationState") -> None:
        for bee in state.bees.values():
            if bee.hive_id != hive_id:
                continue
            bee.state = BeeState.IDLE
            bee.target_flower_id = None
            if bee.carry_target_id:
                target = state.bees.get(bee.carry_target_id)
                if target and bee.id in target.carried_by:
                    target.carried_by.remove(bee.id)
            bee.carry_target_id = None
            bee.carried_by.clear()

    def _build_world_view(
        self,
        hive: Hive,
        bees: List[Bee],
        state: "SimulationState",
        params: "SimParams",
    ) -> WorldView:
        def bee_view(bee: Bee) -> BeeView:
            return BeeView(
                id=bee.id,
                x=round(bee.pos.x, 2),
                y=round(bee.pos.y, 2),
                hive_id=bee.hive_id,
                state=bee.state.value,
                nectar=round(bee.nectar, 3),
                energy=round(bee.energy, 2),
                max_energy=bee.max_energy,
                target_flower_id=bee.target_flower_id,
                carry_target_id=bee.carry_target_id,
                carried_by=tuple(bee.carried_by),
            )

        def flower_view(flower: Flower) -> FlowerView:
            return FlowerView(
                id=flower.id,
                x=round(flower.pos.x, 2),
                y=round(flower.pos.y, 2),
                nectar=round(flower.nectar, 3),
                max_nectar=flower.max_nectar,
                state=flower.state.value,
            )

        def obstacle_view(obstacle: Obstacle) -> ObstacleView:
            return ObstacleView(
                id=obstacle.id,
                x=round(obstacle.pos.x, 2),
                y=round(obstacle.pos.y, 2),
                radius=obstacle.radius,
                kind=obstacle.kind.value,
            )

        return WorldView(
            hive_id=hive.id,
            hive_x=round(hive.pos.x, 2),
            hive_y=round(hive.pos.y, 2),
            hive_nectar=round(hive.nectar, 3),
            hive_honey=round(hive.honey, 3),
            bees=tuple(bee_view(bee) for bee in bees),
            all_bees=tuple(bee_view(bee) for bee in state.bees.values()),
            flowers=tuple(flower_view(flower) for flower in state.flowers.values()),
            obstacles=tuple(obstacle_view(obstacle) for obstacle in state.obstacles.values()),
            canvas_w=params.canvas_w,
            canvas_h=params.canvas_h,
            tick=state.tick_count,
        )
