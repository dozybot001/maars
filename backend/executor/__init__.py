"""
Executor module - task execution + output validation.
Validation is a fixed step after execution; Executor handles both.
"""

from .pools import executor_manager
from .runner import ExecutorRunner

__all__ = [
    "ExecutorRunner",
    "executor_manager",
]
