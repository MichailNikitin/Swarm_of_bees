"""
Пример пользовательского алгоритма — Избирательный (Selective).

═══════════════════════════════════════════════════════════════════
КАК ДОБАВИТЬ СВОЙ АЛГОРИТМ:
═══════════════════════════════════════════════════════════════════
1. Скопируйте этот файл в папку  backend/simulation/algorithms/
   под новым именем, например  my_algo.py

2. Задайте уникальные  name  и  description  у класса.

3. Реализуйте метод  assign_idle_bees(bees, flowers):
   • bees    — список Bee этого улья; меняйте только .state и .target_flower_id
   • flowers — словарь {flower_id: Flower}; НЕ меняйте flower.state
   • Чтобы отправить пчелу к цветку:
         bee.target_flower_id = flower.id
         bee.state = BeeState.TO_FLOWER
   • Пчёл с полным нектаром базовый класс отправляет в улей автоматически.

4. Раскомментируйте / добавьте строку импорта в  __init__.py:
       from .my_algo import MyAlgorithm

5. Перезапустите сервер — алгоритм появится в выпадающем списке ульев.
═══════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

from typing import Dict, List

from .base import BaseSwarmAlgorithm
from .registry import register
from ..agents import Bee, BeeState, Flower, FlowerState

NECTAR_THRESHOLD = 2.0  # Пчёлы летят только к цветкам с нектаром >= этого значения


@register
class SelectiveAlgorithm(BaseSwarmAlgorithm):
    """
    Избирательный алгоритм.

    Пчёлы посещают только цветки, где нектара >= NECTAR_THRESHOLD.
    Если таких цветков нет — ждут (idle), пока цветки не восполнятся.
    Результат: меньше перелётов, каждый — более продуктивный.
    """

    name = "selective"
    description = "Избирательный: только богатые нектаром цветки"

    def assign_idle_bees(
        self,
        bees: List[Bee],
        flowers: Dict[str, Flower],
    ) -> None:
        self._assign_balanced(
            bees,
            flowers,
            lambda bee, flower, load, capacity:
                flower.nectar * 11.0 - bee.pos.distance_to(flower.pos) / 11.0,
            min_nectar=NECTAR_THRESHOLD,
        )
