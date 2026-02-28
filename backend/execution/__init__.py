"""
Execution module - task execution + output validation.
Validation is a fixed step after execution; workers handle both.
"""

from .pools import worker_manager
from .runner import ExecutionRunner

__all__ = [
    "ExecutionRunner",
    "worker_manager",
]
