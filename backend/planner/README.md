# Planner 模块

递归分解用户 idea 为可执行的原子任务树。

## 流程

```
task "0"（idea）
  → Atomicity Check → 非原子 → Decompose → 子任务递归
                     → 原子   → Format（生成 input/output）
```

1. **Atomicity**：判断任务是否可直接执行（原子性）。接收 depth、ancestor_path、idea、siblings 等上下文，按阶段边界做粒度判断；temperature=0 保证一致性。
2. **Decompose**：按实际阶段边界分解，通常 2–6 个子任务；子任务仅含同级依赖（不依赖父任务）。优先保证边界清晰、职责单一。
3. **Format**：为原子任务生成 input/output 规范及验证标准

## 示例 idea

`Compare Python vs JavaScript for backend development and summarize pros/cons.` — 可分解为：调研 Python 生态、调研 JavaScript 生态、对比并撰写报告。

## task_id 规则

- `0`：用户输入的 idea
- `1, 2, 3, 4`：顶层子任务
- `1_1, 1_2`：任务 1 的子任务
- `1_1_1, 1_1_2`：任务 1_1 的子任务

## 依赖规则

- 子任务**不**依赖父任务（分解关系 ≠ 依赖关系）
- 依赖仅在同级兄弟间建立
- 非原子任务的依赖在生成 execution 时由 `from_plan.py` 继承下沉至原子后代

## 文件

| 文件 | 用途 |
|------|------|
| index.py | run_plan 主流程，递归 atomicity/decompose/format |
| llm_client.py | OpenAI 兼容 API 调用 |
| prompts/atomicity-prompt.txt | 原子性判断 prompt（含边界示例、上下文说明） |
| prompts/decompose-prompt.txt | 任务分解 prompt（边界优先、职责单一） |
| prompts/format-prompt.txt | 原子任务格式化 prompt |
| prompts/quality-assess-prompt.txt | 质量评估 prompt |
