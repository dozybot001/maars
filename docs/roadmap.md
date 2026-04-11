# MAARS Roadmap（LangGraph 版）

> **总目标**：用 LangGraph 重写 MAARS，思想不变（见 [`concept.md`](concept.md)），实现完全按 LangGraph 原生方式来（见 [`architecture.md`](architecture.md)）。
>
> **阶段原则**：先跑通最简单的 graph（Refine），再做对称的 Write，最后啃最复杂的 Research。每个里程碑都要有"可跑的端到端产物"，不做无法运行的中间态。

## 0. 当前状态

- ✅ 分支创建完成（`langgraph`）
- ✅ 代码清零完成，文档优先（doc-first）
- ✅ 5 份设计文档骨架就位
- ✅ **M1 Refine 完成 + polished**：端到端可跑，增量 feedback 语义已对齐原 MAARS IterationState 设计
- ⏸ **M2 Write 暂停**：实现曾验证过（commit `06584f3` 4 轮 passed=True），现已砍掉代码聚焦 M1 打磨
- ⏳ **M3 Research 未开始**

## 1. 里程碑

### M0 · 设计对齐 ✅

- [x] **拍板 Model provider**：Gemini only（`gemini-3-flash-preview`） — 2026-04-12
- [x] 生成 `.env` 模板和依赖清单 — 2026-04-12
- [ ] 拍板：三阶段衔接方案 A / B（或者明确"先 A 再看"） — 推迟到 M5 前

---

### M1 · Refine graph 可跑 ✅

**目标**：一个命令，输入一个 `raw_idea`，输出 `refined_idea`。Explorer ↔ Critic 对抗能跑通。

**范围**（分 6 Step，全部完成）：

- [x] **Step 1** 项目骨架（`pyproject.toml`、`src/maars/` 目录、`cli.py` hello 命令）
- [x] **Step 2** `RefineState` TypedDict + `Issue` Pydantic + `get_chat_model()` 工厂 + `sanity` 命令
- [x] **Step 3** `critic` node（纯 LLM judge + `with_structured_output`） + `critique` 命令
- [x] **Step 4** `explorer` node（Gemini + 内置 `google_search` grounding，不走 ReAct loop） + `draft` 命令
- [x] **Step 5** Refine `StateGraph` 编译 + `AsyncSqliteSaver` 异步 checkpointer
- [x] **Step 6** CLI `refine` 命令：流式打印 + resume
- [x] **M1.1 polish**：deserialize warning fix + Critic id rule + `--from-file` 支持 + `(debug)` CLI 标签
- [x] **Refactor**：增量 feedback 语义（Critic 返回 delta，系统维护 state.issues）
- [x] **CLI UX polish**：自动 thread id（`refine-NNN` 编号）、`data/refine/{NNN}/` 结构化 session 目录、砍掉 `--fresh` 冗余 flag

**验证**：已跑过多个不同的 `raw_idea`，迭代收敛合理（resolved 数量稳定接近 prior，id 严格递增）。

**当前状态**：等待用户实际测试 + 反馈。

---

### M2 · Write graph 可跑（独立） ⏸ Paused

> **2026-04-12 暂停**：M2 的 Writer ↔ Reviewer 结构曾在 commit `06584f3` 验证过 4 轮收敛到 `passed=True`，但为了集中精力打磨 M1 Refine、减小认知负担，Write 实现已从 codebase 砍掉。待 Refine 在真实使用中稳定后再重启 M2。
>
> 相关代码文件已删除（`graphs/write.py`、`agents/{writer,reviewer}.py`、`prompts/{writer,reviewer}.py`、`WriteState` TypedDict），但设计文档 [`docs/graph.md §3 Write Graph`](graph.md) 保留作为将来恢复时的参考。

**目标**：给定一个 `refined_idea` + 一个假的 `artifacts_dir`（手动构造的实验结果），跑 Writer ↔ Reviewer 对抗，输出 `paper.md`。

**范围**（恢复时重新实现）：

- [ ] `WriteState` 定义
- [ ] `writer` node（要能读 `artifacts_dir` 里的文件）
- [ ] `reviewer` node（学术评审视角的 prompt）
- [ ] CLI：`maars write <idea.md> <artifacts_dir>`

**退出条件**：给定假 artifacts 能产出一篇完整的 paper.md，Reviewer 能推动至少 2 轮修订。

---

### M3 · Research graph 简化版

**目标**：跑通 Research，但不开并行、不做 re-decompose、不做 strategy loop。

**范围**：

- [ ] `ResearchState` 定义
- [ ] `calibrate` / `strategy` / `decompose`（单轮，不循环）
- [ ] `execute` **串行**版本（for loop，不用 Send）
- [ ] `verify` 只做 retry，不做 re-decompose
- [ ] `evaluate` 只打分，不循环回 strategy
- [ ] 代码执行 tool：**本地 subprocess**，不做 Docker 沙箱

**刻意省略的东西**：

- ❌ `Send` 并行（M4 再加）
- ❌ `re-decompose` 分支（M4）
- ❌ `strategy_update` 循环（M4）
- ❌ Docker 沙箱（M4 或更晚）

**退出条件**：一个简单研究想法 → 一组实验结果，虽然串行慢但跑通。

---

### M4 · Research graph 完整版

**目标**：加回 M3 省略的东西。

- [ ] `Send` API 并行 execute
- [ ] `task_results` 的 dict-merge reducer
- [ ] `verify` 的 re-decompose 分支
- [ ] `evaluate` 的 strategy_update 循环
- [ ] Docker 沙箱（如果决定做）

**退出条件**：能跑 5+ 原子任务的研究目标，并行正确 fan-in，strategy 能自动调整。

---

### M5 · 端到端三阶段串联

**目标**：`maars run "想法"` → paper.md，全自动。

**前置**：M2 Write 必须先恢复。在这之前必须定 [`architecture.md §4`](architecture.md#4-未决问题) 的"三阶段衔接"方案 A / B。

- [ ] 顶层 orchestrator graph（或文件衔接方案）
- [ ] 端到端的 CLI 入口
- [ ] 端到端 checkpoint + resume
- [ ] 至少 1 个完整的端到端跑通案例存档

**退出条件**：完整 pipeline 能跑通且结果像样。

---

### M6+ · 可选增强

不是 MVP 必须，按需启用：

- [ ] 前端（FastAPI / LangServe / LangGraph Studio 三选一）
- [ ] 多 provider 抽象层（当前是 Gemini only，若需要再加）
- [ ] 外部 search tool（Tavily 等，当前用 Gemini 内置 grounding）
- [ ] Human-in-the-loop interrupt 点
- [ ] 英文文档和多语言 prompt
- [ ] 发布和文档站

## 2. 不做什么（明确排除）

这一节比"要做什么"更重要——防止范围蔓延。

| 不做 | 理由 |
|---|---|
| **多语言文档**（中英双语） | 原 MAARS 的翻译维护成本很重，MVP 阶段只维护中文 |
| **前端**（MVP 阶段） | 前端是原 MAARS 最重的包袱，LangGraph stream 在 CLI 下完全够观察 |
| **多 provider 抽象层** | Step 3 验证 Gemini 3 structured output 稳定，单 provider 够用 |
| **外部 search tool**（Tavily 等） | Explorer 用 Gemini 内置 grounding，省掉外部 API key 和依赖 |
| **`create_react_agent` / ReAct loop** | Explorer 一次 invoke + grounding 就够 |
| **M2 Write 实现**（当前） | 暂停，先打磨 Refine（见 M2） |
| **继承 `IterationState` / `Stage` 等原架构接口** | 换 LangGraph 的意义就是不用自建 runtime |
| **Agno 框架** | 要纯粹体验 LangGraph |
| **Docker 沙箱**（M3 之前） | M3 用本地 subprocess 先跑通 |
| **发版、Release Notes、CHANGELOG** | 发版机制等 M5 后再考虑 |

## 3. 时间感（非承诺）

| 里程碑 | 估计工作量 | 实际 |
|---|---|---|
| M0 设计对齐 | 0.5-1 天 | ~0.5 天 |
| M1 Refine | 2-3 天 | ~2 天（含 polish 和 incremental refactor） |
| M1 用户测试 + 打磨 | 0.5 天 | **正在进行** |
| M2 Write | 1-2 天 | 实现过一次（已 paused） |
| M3 Research 简化 | 3-4 天 | — |
| M4 Research 完整 | 3-5 天 | — |
| M5 端到端 | 1-2 天 | — |

---

<!-- TODO: Refine 用户测试完成后，决定下一步是 M3 Research 还是恢复 M2 Write -->
