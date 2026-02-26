# MAARS Backend

运行方式见项目根 [README](../README.md#快速开始)。

## 结构

| 目录 | 职责 |
|------|------|
| [api/](api/) | 路由、schemas、共享状态 |
| [shared/](shared/) | 公共工具（graph 等） |
| [planner/](planner/) | AI 规划：atomicity → decompose → format |
| [monitor/](monitor/) | 执行图生成与布局 |
| [executor/](executor/) | 任务执行与调度 |
| [validator/](validator/) | 输出验证工作池 |
| [db/](db/) | 文件存储 |
| [test/](test/) | Mock 与测试 |

## 数据流

```
plan.json ← Planner     execution.json ← Monitor     Execution → 状态更新
```
