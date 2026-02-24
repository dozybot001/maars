"""Layout module - computes graph layouts for task trees."""

from .stage_layout import compute_stage_layout
from .tree_layout import compute_decomposition_layout


def compute_monitor_layout(tasks):
    """Stage-based layout (monitor/execution view)."""
    return compute_stage_layout(tasks)


__all__ = [
    "compute_decomposition_layout",
    "compute_monitor_layout",
    "compute_stage_layout",
]
