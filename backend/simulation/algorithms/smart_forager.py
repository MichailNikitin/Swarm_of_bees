"""Built-in command-based algorithm with global task coordination."""
from __future__ import annotations

import math

from ..commands import BeeCommand, CommandDict, WorldView
from .command_base import CommandAlgorithm
from .registry import register


def _dist(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


def _angle(ax: float, ay: float, bx: float, by: float) -> float:
    return math.atan2(by - ay, bx - ax)


@register
class SmartForagerAlgorithm(CommandAlgorithm):
    name = "smart_forager"
    description = "Умный фуражир (команды)"

    def compute_commands(self, view: WorldView) -> CommandDict:
        commands: CommandDict = {}
        open_flowers = [f for f in view.flowers if f.state == "open"]
        hive_bees = list(view.bees)
        target_loads: dict[str, int] = {}

        for bee in hive_bees:
            if bee.target_flower_id and bee.state in ("moving", "to_flower", "collecting"):
                target_loads[bee.target_flower_id] = target_loads.get(bee.target_flower_id, 0) + 1

        unconscious = [b for b in view.all_bees if b.state == "unconscious"]
        rescue_targets = sorted(
            unconscious,
            key=lambda b: (len(b.carried_by), _dist(view.hive_x, view.hive_y, b.x, b.y)),
        )

        for bee in sorted(hive_bees, key=lambda b: (-b.energy, b.id)):
            at_hive = _dist(bee.x, bee.y, view.hive_x, view.hive_y) <= 56.0

            if bee.state == "carrying" and bee.carry_target_id:
                commands[bee.id] = BeeCommand("move", _angle(bee.x, bee.y, view.hive_x, view.hive_y))
                continue

            if bee.energy <= 20.0 and at_hive:
                commands[bee.id] = BeeCommand("rest")
                continue
            if bee.energy <= 20.0:
                commands[bee.id] = BeeCommand("move", _angle(bee.x, bee.y, view.hive_x, view.hive_y))
                continue

            if bee.nectar >= 1.0 and at_hive:
                commands[bee.id] = BeeCommand("unload")
                continue
            if bee.nectar >= 1.0:
                commands[bee.id] = BeeCommand("move", _angle(bee.x, bee.y, view.hive_x, view.hive_y))
                continue

            rescue_target = next(
                (
                    target for target in rescue_targets
                    if target.id != bee.id and len(target.carried_by) < 2 and bee.id not in target.carried_by
                ),
                None,
            )
            if rescue_target is not None:
                dist = _dist(bee.x, bee.y, rescue_target.x, rescue_target.y)
                if dist <= 20.0:
                    commands[bee.id] = BeeCommand("pickup", target_id=rescue_target.id)
                else:
                    commands[bee.id] = BeeCommand(
                        "move",
                        _angle(bee.x, bee.y, rescue_target.x, rescue_target.y),
                    )
                continue

            nearby_flower = next(
                (
                    flower for flower in open_flowers
                    if _dist(bee.x, bee.y, flower.x, flower.y) <= 20.0 and flower.nectar > 0
                ),
                None,
            )
            if nearby_flower is not None:
                commands[bee.id] = BeeCommand("collect")
                continue

            best_flower = None
            best_score = float("-inf")
            for flower in open_flowers:
                distance = _dist(bee.x, bee.y, flower.x, flower.y)
                load = target_loads.get(flower.id, 0)
                capacity = max(1, min(4, int(flower.nectar / 1.5) + 1))
                score = flower.nectar * 10.0 - distance / 8.0 - (load / capacity) * 6.0
                if score > best_score:
                    best_score = score
                    best_flower = flower

            if best_flower is None:
                commands[bee.id] = BeeCommand("idle")
                continue

            target_loads[best_flower.id] = target_loads.get(best_flower.id, 0) + 1
            commands[bee.id] = BeeCommand(
                "move",
                _angle(bee.x, bee.y, best_flower.x, best_flower.y),
            )

        return commands
