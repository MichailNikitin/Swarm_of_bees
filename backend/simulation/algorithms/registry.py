"""Algorithm registry — maps names to classes."""
from __future__ import annotations

from typing import Dict, List, Type

from .base import BaseSwarmAlgorithm

_REGISTRY: Dict[str, Type[BaseSwarmAlgorithm]] = {}


def register(cls: Type[BaseSwarmAlgorithm]) -> Type[BaseSwarmAlgorithm]:
    """Class decorator — register an algorithm by its .name attribute."""
    if not cls.name:
        raise ValueError(f"{cls.__name__} must define a non-empty 'name'")
    _REGISTRY[cls.name] = cls
    return cls


def get_algorithm(name: str) -> BaseSwarmAlgorithm:
    """Return a fresh instance of the named algorithm (fallback: first registered)."""
    cls = _REGISTRY.get(name)
    if cls is None:
        cls = next(iter(_REGISTRY.values()))
    return cls()


def list_algorithms() -> List[dict]:
    """Return metadata list for all registered algorithms."""
    return [
        {"name": cls.name, "description": cls.description}
        for cls in _REGISTRY.values()
    ]
