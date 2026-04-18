"""Restricted execution environment for user-defined command algorithms."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from ..commands import BeeCommand, CommandDict, WorldView


@dataclass
class SandboxResult:
    commands: CommandDict
    error: str | None = None
    debug_logs: list[str] | None = None


def cmd(action: str, angle: float = 0.0, speed: float = 1.0, target_id: str = "") -> BeeCommand:
    return BeeCommand(action=action, angle=angle, speed_factor=speed, target_id=target_id)


SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "range": range,
    "reversed": reversed,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "Exception": Exception,
    "RuntimeError": RuntimeError,
    "ValueError": ValueError,
    "zip": zip,
}


def _sandbox_namespace(debug_logs: list[str] | None = None) -> dict[str, Any]:
    def debug(*parts: Any) -> None:
        if debug_logs is None:
            return
        debug_logs.append(" ".join(str(part) for part in parts))

    return {
        "__builtins__": SAFE_BUILTINS,
        "math": math,
        "cmd": cmd,
        "debug": debug,
        "BeeCommand": BeeCommand,
    }


def validate_user_code(source: str) -> tuple[bool, str]:
    try:
        code = compile(source, "<user_algorithm>", "exec")
    except SyntaxError as exc:
        return False, f"SyntaxError: {exc.msg} (line {exc.lineno})"

    namespace = _sandbox_namespace()
    try:
        exec(code, namespace, namespace)
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"

    tick = namespace.get("tick")
    if not callable(tick):
        return False, "Функция tick(view) не найдена."
    return True, ""


def execute_user_code(source: str, view: WorldView) -> SandboxResult:
    try:
        code = compile(source, "<user_algorithm>", "exec")
    except SyntaxError as exc:
        return SandboxResult({}, f"SyntaxError: {exc.msg} (line {exc.lineno})", [])

    debug_logs: list[str] = []
    namespace = _sandbox_namespace(debug_logs)
    try:
        exec(code, namespace, namespace)
        tick = namespace.get("tick")
        if not callable(tick):
            return SandboxResult({}, "Функция tick(view) не найдена.", debug_logs)
        raw = tick(view)
    except Exception as exc:
        return SandboxResult({}, f"{type(exc).__name__}: {exc}", debug_logs)

    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        return SandboxResult({}, "tick(view) должен возвращать dict вида {bee_id: BeeCommand}.", debug_logs)

    commands: CommandDict = {}
    for bee_id, value in raw.items():
        if isinstance(value, BeeCommand):
            commands[str(bee_id)] = value
        elif isinstance(value, dict):
            commands[str(bee_id)] = BeeCommand(
                action=str(value.get("action", "idle")),
                angle=float(value.get("angle", 0.0)),
                speed_factor=float(value.get("speed_factor", value.get("speed", 1.0))),
                target_id=str(value.get("target_id", "")),
            )
        else:
            return SandboxResult({}, f"Некорректная команда для пчелы {bee_id}.", debug_logs)

    return SandboxResult(commands, None, debug_logs)
