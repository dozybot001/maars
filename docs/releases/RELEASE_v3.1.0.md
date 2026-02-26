**发布日期**：2026-02-26

## 概述

本版本对后端进行按区域重构，将 `layout`、`tasks`、`workers` 拆分为 `planner`、`monitor`、`executor`、`validator` 四大区域，并补充各目录 README 文档。

## 新增功能 (Added)

- **shared/**：新增公共模块，`graph.py` 提供 `build_dependency_graph`、`natural_task_id_key`，供 planner、monitor 共用
- **文档**：各模块目录新增 README（api、db、shared、planner/layout、planner/prompts、monitor/layout、monitor/tasks、executor/execution、test/mock-ai 等）

## 变更 (Changed)

- **后端结构**：按 planner、monitor、executor、validator 区域解耦
- **planner**：新增 `layout/tree_layout.py`，分解树布局从根 layout 迁入
- **monitor**：新增 `layout/stage_layout.py`、`tasks/task_stages.py`、`tasks/task_cache.py`，执行图布局与任务阶段计算迁入
- **executor**：从 workers 拆分，含 runner、execution、executor_manager
- **validator**：从 workers 拆分，含 validator_manager
- **文档**：backend/README 精简为目录表，各模块 README 统一风格、避免冗余
- **.gitignore**：新增 `*.qkdownloading` 忽略下载临时文件

## 移除 (Removed)

- **layout/**：已拆分至 planner/layout、monitor/layout、shared
- **tasks/**：已迁入 monitor/tasks
- **workers/**：已拆分至 executor、validator

## 技术细节 / 迁移指南

- **导入路径**：若外部代码直接引用 `layout`、`tasks`、`workers`，需改为 `planner.layout`、`monitor.layout`、`monitor.tasks`、`executor`、`validator`、`shared.graph`
- **API 行为**：无变更，路由与响应格式保持兼容
- **配置**：无变更
