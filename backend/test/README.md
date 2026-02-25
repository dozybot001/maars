# Test 模块

Mock AI 响应，无需真实 API 即可运行完整流程。

## mock-ai

Planner 各阶段的预设响应（按 task_id 匹配，未命中则用 `_default`）：

| 文件 | 用途 |
|------|------|
| atomicity.json | 原子性判断结果 |
| decompose.json | 任务分解结果（含同级依赖） |
| format.json | 原子任务的 input/output 规范 |

每条包含 `content`（JSON 结果）和 `reasoning`（流式输出到前端 thinking 区域）。

## mock_stream.py

模拟 LLM 流式输出：reasoning 分块通过 on_thinking 回调发送。
