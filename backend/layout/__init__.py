"""Layout module - computes graph layouts for task trees."""

from .sugiyama import compute_layout as compute_sugiyama_layout
from .tree_layout import compute_decomposition_layout


def compute_tree_layout(tasks):
    """Dependency-based layout (monitor/execution view). Sugiyama layered DAG."""
    return compute_sugiyama_layout(tasks)


__all__ = ["compute_tree_layout", "compute_decomposition_layout"]
