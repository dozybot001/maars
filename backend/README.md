# MAARS Backend

运行方式见项目根 [README](../README.md#快速开始)。

## 结构

| 目录 | 职责 |
|------|------|
| api/ | 路由、schemas、共享状态 |
| plan/ | AI 规划：atomicity → decompose → format；含 visualization（分解树、执行图布局） |
| execution/ | 任务执行与调度（Execute → Validate） |
| db/ | 文件存储：db/{plan_id}/ |
| test/ | Mock AI |

## 数据流

```
plan.json ← plan     execution.json ← plan (visualization)     execution → 状态更新
```
