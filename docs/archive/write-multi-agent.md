# Write Stage Multi-Agent 重设计

> v9.1.0 计划，待实施

## 目标

将 Write 阶段从单 session 写作改为多 agent 协作写作，提升论文深度和质量。

## 流程

```
Outline Agent
  ↓ outline.json（章节列表 + 每章的目标和分配的 task 输出）
Section Agent × N（并行）
  ↓ write/{section_id}.md（每章独立撰写）
系统拼接
  ↓ paper_draft.md
Polish Agent（读取 outline + 所有章节）
  ↓ 逐章反馈：信息缺口、内容重叠、衔接问题、深度不足
Section Agent 修订（仅被标记的章节）
  ↓ write/{section_id}.md 更新
系统重新拼接
  ↓ paper.md
```

## 各 Agent 职责

### Outline Agent
- 读取 refined_idea + 所有 task 输出 + artifacts 列表
- 输出结构化 outline：每个章节有 id、标题、目标描述、分配的 task ID、预期引用的 artifacts
- 决定论文结构（不套模板，让内容决定章节）
- 指定每章的最低字数要求

### Section Agent（每章一个，并行执行）
- 输入：本章的 outline 条目 + 分配的 task 输出（通过工具读取）
- 只写自己负责的章节，不看其他章节
- 嵌入相关的图表和数据
- 产出保存到 `write/{section_id}.md`

### Polish Agent
- 读取 outline 和所有已完成章节
- 全局视角审查：
  - 章节间衔接是否自然
  - 是否有信息在多章重复
  - 是否有 task 产出没被任何章节引用（遗漏）
  - 数字、术语、引用是否一致
  - 各章是否达到深度要求
- 输出逐章的结构化反馈（JSON：section_id → feedback）
- 没问题的章节标记 pass，有问题的给出具体修改意见

### 系统拼接
- 按 outline 顺序拼接所有 `write/{section_id}.md`
- 加入论文标题、摘要（由 Outline Agent 预写或 Polish Agent 最后补）
- 产出 `paper.md`

## 预期效果

1. **论文更长更深**：每个 section agent 专注自己的章节，有足够 context 窗口展开论述，不会因为要写全文而压缩每章
2. **并行加速**：多章同时写作，和 Research 的并行 Execute 一样
3. **质量可控**：Polish Agent 做全局审查，能发现单 agent 写全文时不会注意到的衔接问题
4. **可观测**：每章独立保存到 DB，进度可见，可单独重试

## DB 结构扩展

```
results/{id}/
├── ...existing...
├── write/
│   ├── outline.json       ← Outline Agent 产出
│   ├── abstract.md        ← Section Agent
│   ├── introduction.md    ← Section Agent
│   ├── methodology.md     ← Section Agent
│   ├── results.md         ← Section Agent
│   ├── conclusion.md      ← Section Agent
│   └── references.md      ← Section Agent
├── paper_draft.md          ← 首次拼接
└── paper.md                ← Polish 后最终版
```

## 进度条

Write 阶段内部可以展示子进度（类似 Research 的 Execute）：
- Outline → Section 1 / Section 2 / ... → Polish → Done

## 与 Research 的对称性

| 概念 | Research | Write |
|------|----------|-------|
| 规划 | Decompose → plan.json | Outline → outline.json |
| 并行执行 | Task agents → tasks/*.md | Section agents → write/*.md |
| 质量审查 | Evaluate（分数驱动） | Polish（内容驱动） |
| 反馈修订 | Replan + 补充 task | 逐章反馈 + 修订 |
| 拼接产出 | _build_final_output() | 系统拼接 → paper.md |
