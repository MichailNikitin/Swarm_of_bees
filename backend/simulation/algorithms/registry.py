"""Algorithm registry — maps names to classes."""
from __future__ import annotations

import re
from typing import Dict, List, Type

from .base import BaseSwarmAlgorithm
from .sandbox import validate_user_code
from .user_algorithm import UserAlgorithm

_REGISTRY: Dict[str, Type[BaseSwarmAlgorithm]] = {}
_USER_ALGORITHMS: Dict[str, UserAlgorithm] = {}


def register(cls: Type[BaseSwarmAlgorithm]) -> Type[BaseSwarmAlgorithm]:
    """Class decorator — register an algorithm by its .name attribute."""
    if not cls.name:
        raise ValueError(f"{cls.__name__} must define a non-empty 'name'")
    _REGISTRY[cls.name] = cls
    return cls


def get_algorithm(name: str) -> BaseSwarmAlgorithm:
    """Return a fresh instance of the named algorithm (fallback: first registered)."""
    if name in _USER_ALGORITHMS:
        algo = _USER_ALGORITHMS[name]
        return UserAlgorithm(algo.name, algo.description, algo.source)
    cls = _REGISTRY.get(name)
    if cls is None:
        cls = next(iter(_REGISTRY.values()))
    return cls()


def list_algorithms() -> List[dict]:
    """Return metadata list for all registered algorithms."""
    builtins = [
        {"name": cls.name, "description": cls.description, "user_defined": False}
        for cls in _REGISTRY.values()
    ]
    users = [
        {"name": algo.name, "description": algo.description, "user_defined": True}
        for algo in _USER_ALGORITHMS.values()
    ]
    return builtins + users


def register_user_algorithm(name: str, description: str, source: str) -> tuple[bool, str]:
    clean_name = name.strip()
    clean_description = description.strip() or clean_name
    if not clean_name:
        return False, "Имя алгоритма обязательно."
    if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{1,63}", clean_name):
        return False, "Имя должно начинаться с буквы и содержать только латиницу, цифры и _. "
    if clean_name in _REGISTRY:
        return False, "Алгоритм с таким именем уже существует среди встроенных."
    ok, error = validate_user_code(source)
    if not ok:
        return False, error
    _USER_ALGORITHMS[clean_name] = UserAlgorithm(clean_name, clean_description, source)
    return True, ""


def remove_user_algorithm(name: str) -> None:
    _USER_ALGORITHMS.pop(name, None)


def get_user_algorithm_source(name: str) -> str | None:
    algo = _USER_ALGORITHMS.get(name)
    return None if algo is None else algo.source
