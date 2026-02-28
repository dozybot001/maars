"""
Task Agent 单轮 LLM 实现 - 任务执行。
Agent 实现放在 task_agent/，单轮 LLM 放在 task_agent/llm/。
"""

from .executor import execute_task

__all__ = ["execute_task"]
