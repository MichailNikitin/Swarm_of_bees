"""Dynamic wrapper around user-provided command-based code."""
from __future__ import annotations

from ..commands import CommandDict, WorldView
from .command_base import CommandAlgorithm
from .sandbox import execute_user_code


class UserAlgorithm(CommandAlgorithm):
    def __init__(self, name: str, description: str, source: str) -> None:
        self.name = name
        self.description = description
        self.source = source
        self.last_error: str | None = None
        self.last_debug: list[str] = []
        self.user_defined = True

    def compute_commands(self, view: WorldView) -> CommandDict:
        result = execute_user_code(self.source, view)
        self.last_error = result.error
        self.last_debug = result.debug_logs or []
        return result.commands if result.error is None else {}
