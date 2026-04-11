# MAARS 核心思想

> 这份文档是**思想的继承**，不是架构。它描述 MAARS 为什么这么做、为什么分三段、为什么每段要对抗、为什么要分解验证——这些决定独立于实现框架（无论是原来的手写 runtime + Agno，还是现在的 LangGraph）。
>
> 实现层面的翻译见 [`architecture.md`](architecture.md) 和 [`graph.md`](graph.md)。

## 1. 问题与目标

**输入**：一个模糊的研究想法（可能只是一句话，或一个 Kaggle 比赛链接）。

**输出**：一篇结构化的研究论文 `paper.md`，以及可复现的代码、数据、图表。

**约束**：全程自主运行，不依赖人类在循环中间做决策。系统必须能自己判断"这个想法够不够清晰可执行"、"这份实验结果够不够强"、"这篇草稿够不够严谨"。

## 2. 核心原则

### 2.1 runtime 管控制流，agent 管开放任务

这是 MAARS 最底层的分工：

- **确定性的东西交给代码**：`if` / `for` / `while` 循环、调度、重试、迭代终止条件——这些写成代码，可读、可测、可回放。
- **开放性的东西交给 LLM**：文献检索、假设生成、代码实验、论文起草、同行评审——这些由 Agent 完成，因为它们本质上需要开放性的判断力。

这个原则比任何具体框架都重要。换 LangGraph 重写的时候，**这个分工不变**——LangGraph 的 `StateGraph` 正是这个原则的天然表达：graph 结构是确定的控制流，node 内部可以装任何开放性的 LLM 调用。

### 2.2 三阶段分工：Refine / Research / Write

一个研究流程可以粗略分成三个关注点：

| 阶段 | 关注点 | 为什么要独立 |
|---|---|---|
| **Refine** | 想法 → 可执行的研究目标 | 模糊的想法不能直接跑实验。先把"我想研究大模型的推理能力"精炼成"在 GSM8K 上对比 Chain-of-Thought 和 Direct Prompting 的 accuracy，控制变量：模型尺寸和样本数量"。 |
| **Research** | 执行研究目标 → 拿到实验结果 | 这是最重的阶段：要设计实验、写代码、跑训练/评测、解释结果。必须能容错和迭代。 |
| **Write** | 实验结果 → 完整论文 | 有实验结果不等于有论文。综合多个实验的叙事、讨论 limitation、对比相关工作，这是一类独立的能力。 |

三阶段之间通过持久化文件衔接：上一阶段的产出落盘，下一阶段从盘上读取。这样每个阶段都可以独立重跑、独立调试，互相之间不共享进程内状态。

### 2.3 迭代对抗循环：primary ↔ reviewer

Refine 和 Write 共享同一个模式：

```
Primary -- draft --> Reviewer
Reviewer -- issues / pass --> Primary
(loop until pass)
```

- **Refine**：Explorer 提案 ↔ Critic 挑刺
- **Write**：Writer 起草 ↔ Reviewer 审稿

**为什么要对抗**？因为单个 Agent 会陷入自己的思维惯性，倾向于认为自己的产出已经够好。对抗循环引入一个独立视角，持续施加"还不够好"的压力，直到满足某个客观终止条件（所有 issue 都 resolved / 评审者 pass）。

**这不是简单的自我反思**。关键区别是：primary 和 reviewer 有不同的 prompt、不同的角色、不同的评价标准。他们是两个 Agent，不是同一个 Agent 的两次调用。

### 2.4 分解验证循环：decompose → execute ↔ verify → evaluate

Research 阶段比 Refine/Write 复杂得多，因为它要执行真实的代码和实验。它的模式是：

```
Decompose  -- 把研究目标拆成原子任务 -->
Execute    -- 每个原子任务跑一遍 -->
Verify     -- 检查产出是否符合预期 -->
  ├── 通过 → 下一任务
  ├── 失败 → 重试 Execute
  └── 致命错误 → 回到 Decompose 重新拆
Evaluate   -- 所有任务完成后，整体评估 -->
  ├── 结果不够强 → 更新 Strategy，重启一轮
  └── 结果够强 → 进入 Write
```

**三个关键设计**：

1. **原子任务是可验证的**。分解到这样一个粒度：每个任务可以单独跑、可以单独判断对错。"跑完整个实验"不是原子任务，"在 GSM8K 上对 GPT-4 采样 100 条并保存"是原子任务。
2. **Verify 和 Execute 是两个角色**。Execute 负责跑通；Verify 负责判断产出是否满足任务定义。这又是一个对抗模式的变体。
3. **Strategy 层允许整体调头**。如果 Evaluate 认为这一轮的整体结果不够强（比如基线太弱、对比不显著），Strategy 可以更新，整个 Research 阶段再跑一轮。这是跳出局部最优的唯一机制。

## 3. 思想来源

原 MAARS 的这些设计沉淀自几轮迭代，过程中有不少思考和废案，主要资料保留在：

- [`archive/multi-agent-design.md`](archive/multi-agent-design.md)
- [`archive/prompt-engineering.md`](archive/prompt-engineering.md)
- [`archive/research-workflow.md`](archive/research-workflow.md)
- [`archive/write-multi-agent.md`](archive/write-multi-agent.md)
- [`archive/CN/architecture.md`](archive/CN/architecture.md) — v13.4.0-agno 的最终架构文档

**读这些 archive 时的心态**：把它们当成"先辈写的设计笔记"。思想可以继承，数据结构、接口、命名约定都不要直接抄——新版本要按 LangGraph 的方式重新设计。

## 4. 这份文档不写什么

- ❌ 不写具体的 State schema、Node 签名、Edge 条件——那些在 [`graph.md`](graph.md)
- ❌ 不写技术选型（为什么用 LangGraph、为什么用 SQLite checkpointer）——那些在 [`architecture.md`](architecture.md)
- ❌ 不写进度和里程碑——那些在 [`roadmap.md`](roadmap.md)

这份文档只回答一个问题：**MAARS 这个系统想解决什么、用什么思想解决**。

---

<!-- TODO: 如果后续发现有新的原则（比如 LangGraph 带来了什么新心智），回头补充到第 2 节。 -->
<!-- TODO: 第 2.4 节的 Strategy 层在原 MAARS 里其实有多个版本的实现，要不要在这里展开讨论？等 graph.md 成形后决定。 -->
