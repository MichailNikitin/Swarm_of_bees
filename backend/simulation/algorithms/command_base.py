"""Base class for command-based algorithms."""
from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from ..commands import CommandDict, WorldView
from .base import BaseSwarmAlgorithm

if TYPE_CHECKING:
    from ..agents import Bee, Flower, Hive


class CommandAlgorithm(BaseSwarmAlgorithm):
    is_command_based = True

    def tick(
        self,
        hive: "Hive",
        bees: list["Bee"],
        flowers: dict[str, "Flower"],
    ) -> None:
        return

    def assign_idle_bees(
        self,
        bees: list["Bee"],
        flowers: dict[str, "Flower"],
    ) -> None:
        return

    @abstractmethod
    def compute_commands(self, view: WorldView) -> CommandDict:
        """Return low-level commands for bees belonging to the hive."""
