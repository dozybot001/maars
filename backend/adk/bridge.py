"""
ADK 桥接层：将 MAARS 工具定义与 api_config 转换为 Google ADK 可用格式。
供所有 Agent 的 adk_runner 使用。
工具定义为 flat dict: {"name": ..., "description": ..., "parameters": ...}
"""

import os
from typing import Any, Callable, List

from google.genai import types
from google.adk.tools import BaseTool

from shared.constants import DEFAULT_MODEL


class ExecutorTool(BaseTool):
    """
    将 flat 工具定义与异步 executor 封装为 ADK 可用的 BaseTool。
    executor_fn: async (name: str, args: dict) -> (is_finish: bool, result: str)
    """

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict,
        executor_fn: Callable[..., Any],
    ):
        super().__init__(name=name, description=description)
        self.parameters = parameters
        self.executor_fn = executor_fn

    def _get_declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters_json_schema=self.parameters,
        )

    async def run_async(
        self, *, args: dict[str, Any], tool_context: Any
    ) -> Any:
        is_finish, result = await self.executor_fn(self.name, args)
        return result


def create_executor_tools(
    tools_def: List[dict],
    executor_fn: Callable[..., Any],
) -> List[ExecutorTool]:
    """
    从 flat 工具定义列表创建 ExecutorTool 列表。
    每个 tool_def: {"name": ..., "description": ..., "parameters": ...}
    executor_fn: async (name, args) -> (is_finish, result_str)
    """
    result = []
    for t in tools_def or []:
        name = t.get("name") or ""
        desc = t.get("description") or ""
        params = t.get("parameters") or {"type": "object", "properties": {}}
        result.append(
            ExecutorTool(
                name=name,
                description=desc,
                parameters=params,
                executor_fn=executor_fn,
            )
        )
    return result


def prepare_api_env(api_config: dict) -> None:
    """
    根据 api_config 设置 ADK/Gemini 所需的环境变量。
    ADK 的 Gemini 模型通过环境变量获取 api_key。
    """
    cfg = dict(api_config or {})
    api_key = cfg.get("apiKey") or cfg.get("api_key")
    if api_key:
        os.environ["GOOGLE_API_KEY"] = str(api_key)


def get_model_for_adk(api_config: dict) -> str:
    """
    从 api_config 获取模型标识符，供 ADK Agent 的 model 参数使用。
    """
    cfg = dict(api_config or {})
    return cfg.get("model") or DEFAULT_MODEL
