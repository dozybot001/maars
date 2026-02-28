# MAARS Backend

运行方式见项目根 [README](../README.md#快速开始)。

## 结构

| 目录 | 职责 |
|------|------|
| api/ | 路由、schemas、共享状态 |
| plan/ | AI 规划：atomicity → decompose → format；plan → execution（业务逻辑，写 db） |
| visualization/ | 分解树、执行图布局（只读 db 数据，计算、渲染） |
| execution/ | 任务执行与调度（Execute → Validate） |
| db/ | 文件存储：db/{plan_id}/ |
| shared/ | 共享模块：graph、llm_client、skill_utils、utils |
| test/ | Mock AI |

## 数据流

```
plan.json ← plan     execution.json ← plan (execution_builder)     execution → 状态更新
layout ← visualization (读 db 数据，计算布局)
```
