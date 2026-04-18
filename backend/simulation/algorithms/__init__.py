"""Swarm algorithm package — import all modules to trigger @register."""
from .command_base import CommandAlgorithm
from .greedy import GreedyAlgorithm
from .nearest import NearestAlgorithm
from .round_robin import RoundRobinAlgorithm
from .probabilistic import ProbabilisticAlgorithm
from .custom_example import SelectiveAlgorithm
from .safety import SafetyAlgorithm
from .smart_forager import SmartForagerAlgorithm
from .registry import (
    get_algorithm,
    get_user_algorithm_source,
    list_algorithms,
    register_user_algorithm,
    remove_user_algorithm,
    _REGISTRY,
)

__all__ = [
    "CommandAlgorithm",
    "get_algorithm",
    "get_user_algorithm_source",
    "list_algorithms",
    "register_user_algorithm",
    "remove_user_algorithm",
    "_REGISTRY",
    "GreedyAlgorithm",
    "NearestAlgorithm",
    "RoundRobinAlgorithm",
    "ProbabilisticAlgorithm",
    "SelectiveAlgorithm",
    "SafetyAlgorithm",
    "SmartForagerAlgorithm",
]
