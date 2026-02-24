# Layout 模块

图布局计算，为 Planner 分解树和 Monitor 执行图提供节点坐标与连线。

## 文件

| 文件 | 用途 |
|------|------|
| graph.py | `build_dependency_graph`、`natural_task_id_key`，供 planner、tasks 共用 |
| tree_layout.py | Planner 分解树：按 task_id 层级 level-order 布局 |
| stage_layout.py | Monitor 执行图：按 stage 分层、等价任务合并 |
| STAGE_LAYOUT_RULES.md | 执行图节点排序与对齐规则说明 |

## API

- `compute_decomposition_layout(tasks)`：Planner 视图，基于 task_id 父子关系
- `compute_monitor_layout(tasks)`：Monitor 视图，基于 stage 与 dependencies
- `compute_stage_layout(tasks, ...)`：stage_layout 直接调用，可传 node_w/node_h 等参数

## 输出格式

```python
{
    "nodes": { "task_id": {"x", "y", "w", "h"} 或 {"x","y","w","h","ids"} },  # ids 为合并节点
    "edges": [{"from", "to", "points", "adjacent"}],  # adjacent=False 表示跨层连线
    "width": float,
    "height": float
}
```

详见 [STAGE_LAYOUT_RULES.md](STAGE_LAYOUT_RULES.md)。
