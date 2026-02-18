# Test 模块

测试相关：mock AI、mock data、测试工具。

## mock-ai/

Planner 使用的 mock AI 响应（无真实 API 调用）：

- `verify.json` - 原子性验证（按 task_id）
- `decompose.json` - 任务分解（按 parent task_id）
- `format.json` - atomic 任务的 input/output 格式化（按 task_id）

每条含 `content`（JSON）和 `reasoning`（流式输出到前端 plan-thinking）。

## mock_stream.py

模拟 AI 流式输出：将 reasoning 分块，通过 on_thinking 回调发送。
