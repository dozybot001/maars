# Planner

递归分解 idea 为原子任务树。含可视化区域（三个子视图：Decomposition Tree、Task Grid、Execution Graph）。

## 流程

```
task "0" → Atomicity → 非原子: Decompose → 递归
                 → 原子: Format（input/output）
```

- **Atomicity**：判断是否可直接执行
- **Decompose**：分解为 2–6 个子任务，仅同级依赖
- **Format**：为原子任务生成 input/output 规范

## 文件

| 文件 | 用途 |
|------|------|
| index.py | run_plan 主流程 |
| llm_client.py | OpenAI 兼容 API |
| [layout/](layout/) | Decomposition Tree 布局 |
| [prompts/](prompts/) | LLM prompt 模板 |
| [visualization/](visualization/) | 可视化区域：Task Grid、Execution Graph |
