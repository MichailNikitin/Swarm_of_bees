"""Swarm algorithm package — import all modules to trigger @register."""
from .greedy import GreedyAlgorithm
from .nearest import NearestAlgorithm
from .round_robin import RoundRobinAlgorithm
from .probabilistic import ProbabilisticAlgorithm
from .custom_example import SelectiveAlgorithm
from .registry import get_algorithm, list_algorithms, _REGISTRY

__all__ = [
    "get_algorithm",
    "list_algorithms",
    "_REGISTRY",
    "GreedyAlgorithm",
    "NearestAlgorithm",
    "RoundRobinAlgorithm",
    "ProbabilisticAlgorithm",
    "SelectiveAlgorithm",
]
