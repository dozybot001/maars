# Planner 模块

统一工作流：idea 为 task 0，生成 plan 时写入 task 0，然后进入 verify 阶段。若不够 atomic 则 decompose，若 atomic 则 format。

## 流程：Verify → Decompose（若否）→ Format（若是）

1. **verify(task)** → atomic?
2. **若 atomic** → format(task)
3. **若否** → decompose(task) → 对每个 child 递归 verify → decompose/format

## task_id

- **0**：idea（用户输入）
- **1, 2, 3, 4**：0 的子任务（顶层阶段）
- **1_1, 1_2**：1 的子任务；**1_1_1, 1_1_2**：1_1 的子任务

## 文件说明

| 文件 | 用途 |
|------|------|
| prompts/decompose-prompt.txt | 分解：0 → 1,2,3,4；1 → 1_1,1_2；... |
| prompts/verify-prompt.txt | 验证：是否 atomic |
| prompts/format-prompt.txt | 格式化：atomic 任务的 input/output |
