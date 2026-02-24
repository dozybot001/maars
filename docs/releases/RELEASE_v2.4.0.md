**发布日期**：2026-02-25

## 概述

本版本聚焦 Executor 模块体验升级：支持 LLM 执行时的**流式思考输出**，用户可在执行阶段实时查看 AI 生成过程；同时重构 Executor 区域 UI，新增 AI Thinking 与 Task Output 双栏展示，并补充 Executor 改进规划文档。

## 新增功能 (Added)

- **Executor**：LLM 执行支持流式输出（streaming），通过 `on_thinking` 回调实时推送生成内容至前端
- **Executor**：新增 AI Thinking 区域，展示执行过程中的实时思考内容（支持 Markdown 渲染、代码高亮、节流渲染）
- **Executor**：新增 Task Output 区域，展示每个任务完成后的最终输出
- **WebSocket**：新增 `execution-start`、`executor-thinking`、`executor-output` 事件，用于执行阶段状态与内容推送
- **Mock 模式**：Mock AI 模式下同样支持模拟流式输出，便于本地调试
- **文档**：新增 [Executor 改进规划](backend/workers/EXECUTOR_IMPROVEMENTS.md)，记录 Agent 化与 Agent Skills 接入方向

## 变更 (Changed)

- **Executor UI**：重构 Executor 区域布局，stats 与 chips 分离，AI Thinking 与 Task Output 采用双栏并排展示
- **Executor UI**：新增 Idle 统计展示，优化 executor chips 与 thinking/output 区域样式
- **Runner**：执行开始时 emit `execution-start`，任务完成时 emit `executor-output`，便于前端同步状态
- **Layout**：`stage_layout` 优化空 `slot_positions` 处理逻辑；`tree_layout` 补充居中策略注释
- **API**：`plan.py` 抽取 `_tree_update_payload` 复用 treeData + layout 构建逻辑

## 修复 (Fixed)

- （本版本无专项 Bug 修复）

## 技术细节

- **流式执行**：`llm_executor.execute_task` 新增 `on_thinking` 参数，当传入时启用 `stream=True`，逐 chunk 回调
- **前端模块**：`executor-thinking.js` 负责接收 WebSocket 数据、节流渲染、滚动保持与用户滚动状态检测
