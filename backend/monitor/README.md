# Monitor

从 plan 生成 execution，构建执行图布局。

## 职责

- **build_execution_from_plan**：提取原子任务、解析依赖（继承+下沉）、分 stage
- **build_layout_from_execution**：生成 grid + treeData + layout

## 文件

| 文件 | 用途 |
|------|------|
| from_plan.py | plan → execution |
| timetable.py | 网格布局（stage 列 + 孤立任务区） |
| [layout/](layout/) | 执行图 stage 布局 |
| [tasks/](tasks/) | 拓扑排序、传递规约 |
