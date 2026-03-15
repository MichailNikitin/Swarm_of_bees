"""Swarm Intelligence Controller — dispatches per-hive algorithms each tick."""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List

if TYPE_CHECKING:
    from .engine import SimulationState

from .agents import Bee
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

    def tick(self, state: "SimulationState") -> None:
        # Группируем пчёл по ульям
        hive_bees: Dict[str, List[Bee]] = {hid: [] for hid in state.hives}
        for bee in state.bees.values():
            if bee.hive_id in hive_bees:
                hive_bees[bee.hive_id].append(bee)

        # Запускаем алгоритм для каждого улья
        for hive_id, hive in state.hives.items():
            algo = self._get_instance(hive_id, hive.algorithm_name)
            algo.tick(hive, hive_bees.get(hive_id, []), state.flowers)

    def invalidate(self, hive_id: str) -> None:
        """Вызывается при удалении улья — освобождает кешированный экземпляр."""
        for k in [k for k in self._cache if k.startswith(f"{hive_id}:")]:
            del self._cache[k]

    def _get_instance(self, hive_id: str, algo_name: str) -> BaseSwarmAlgorithm:
        key = f"{hive_id}:{algo_name}"
        if key not in self._cache:
            # Удаляем устаревший экземпляр при смене алгоритма
            for k in [k for k in self._cache if k.startswith(f"{hive_id}:")]:
                del self._cache[k]
            self._cache[key] = get_algorithm(algo_name)
        return self._cache[key]
