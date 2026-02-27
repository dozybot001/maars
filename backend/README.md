# MAARS Backend

运行方式见项目根 [README](../README.md#快速开始)。

## 结构

| 目录 | 职责 |
|------|------|
| api/ | 路由、schemas、共享状态 |
| planner/ | AI 规划：atomicity → decompose → format；含 visualization（执行图） |
| executor/ | 任务执行与调度（Execute → Validate） |
| shared/ | 公共工具（graph） |
| db/ | 文件存储：db/{plan_id}/ |
| test/ | Mock AI |

## 数据流

```
plan.json ← Planner     execution.json ← Planner (visualization)     Execution → 状态更新
```
