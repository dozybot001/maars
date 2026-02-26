**发布日期**：2026-02-26

## 概述

本版本为 **major** 升级：Executor 从单次 LLM 调用升级为支持多轮决策与工具调用的 **Agent 形态**，每个任务在独立沙箱中运行；同时完善 API 配置页，支持 Mock / LLM / LLM+Agent 三种模式的参数化配置。

## 新增功能 (Added)

- **Executor Agent**：新增 LLM + Agent 模式，Executor 使用多轮 ReAct 循环与工具调用（Planner 仍为 LLM 分解）
- **Agent 工具**：ReadArtifact（读取依赖任务输出）、ReadFile（读取 plan 目录及沙箱文件）、WriteFile（写入沙箱）、Finish（提交最终输出）、ListSkills、LoadSkill（Agent Skills 指令注入）
- **沙箱隔离**：每个 task 对应独立沙箱目录 `db/{plan_id}/{task_id}/sandbox/`，工具执行限定于此，支持路径穿越防护
- **API 配置**：AI Mode 配置页支持 Mock / LLM / LLM+Agent 三种模式，各模式提供可调参数
- **Mock 参数**：执行通过率、验证通过率、最大重试次数（原环境变量现可在 UI 配置）
- **LLM 参数**：Planner Temperature、Executor LLM Temperature
- **LLM+Agent 参数**：Planner Temperature、Executor LLM Temperature、Executor Agent 最大轮数
- **LLM 客户端**：`chat_completion` 支持 `tools` 参数及 `tool_calls` 响应，用于 Agent 模式

## 变更 (Changed)

- **配置结构**：`api_config.json` 新增 `modeConfig`，按模式存储可调参数
- **配置解析**：`_resolve_api_config` 合并 `modeConfig`，Runner/Executor 从配置读取参数
- **Executor**：`executorAgentMode=true` 时启用 Agent 循环，`max_turns` 可配置
- **API 配置 UI**：Mock/LLM/LLM+Agent 各模式配置页按模块分组（LLM (Planner)、Executor LLM、Executor Agent）
- **agent_tools**：复用 `db._validate_plan_id`，移除重复实现

## 修复 (Fixed)

- （本版本无专项 Bug 修复）

## 技术细节 / 迁移指南

- **启用 Agent 模式**：API 配置 → AI Mode 选择「LLM + Agent」→ 保存
- **沙箱路径**：`db/{plan_id}/{task_id}/sandbox/`，ReadFile 使用 `sandbox/X` 读取沙箱内文件
- **Skills 目录**：环境变量 `MAARS_SKILLS_DIR` 或默认 `backend/skills/`
- **向后兼容**：旧配置中的 `temperature`、`maxTurns` 自动映射为 `executorLlmTemperature`、`executorAgentMaxTurns`
