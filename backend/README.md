# MAARS Backend

运行方式见项目根 [README](../README.md#快速开始)。

## 结构

| 目录 | 职责 |
|------|------|
| [api/](api/) | 路由、schemas、共享状态 |
| [shared/](shared/) | 公共工具（graph 等） |
| [planner/](planner/) | AI 规划：atomicity → decompose → format |
| [planner/visualization/](planner/visualization/) | 可视化区域：Decomposition Tree、Task Grid、Execution Graph |
| [executor/](executor/) | 任务执行与调度（Execute → Validate 为 Executor 内固定步骤） |
| [planner/skills/](planner/skills/) | Planner Agent 技能（分解模式、研究范围、格式规范） |
| [executor/skills/](executor/skills/) | Executor Agent 技能（find-skills、skill-creator、markdown-reporter 等） |
| [db/](db/) | 文件存储 |
| [test/](test/) | Mock 与测试 |

## 数据流

```
plan.json ← Planner     execution.json ← Planner (visualization)     Execution → 状态更新
```
