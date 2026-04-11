# MAARS Roadmap(LangGraph 版)

> **总目标**:用 LangGraph 重写 MAARS,思想不变(见 [`concept.md`](concept.md)),实现完全按 LangGraph 原生方式来(见 [`architecture.md`](architecture.md))。
>
> **阶段原则**:先跑通最简单的 graph(Refine),再做对称的 Write,最后啃最复杂的 Research。每个里程碑都要有"可跑的端到端产物",不做无法运行的中间态。

## 0. 当前状态

- ✅ 分支创建完成(`langgraph`)
- ✅ 代码清零完成,文档优先(doc-first)
- ✅ 5 份设计文档骨架就位:`README` / `concept` / `architecture` / `graph` / `roadmap`
- ⏳ **等待**:通读文档,对齐设计后再动手编码

## 1. 里程碑

### M0 · 设计对齐(当前)

**目标**:文档读完、有分歧的地方对齐。

- [ ] 通读 `concept.md`——思想是否完整继承,有没有漏掉的原则
- [ ] 通读 `architecture.md`——技术选型是否合理
  - [ ] **拍板 Model provider**(Gemini / Claude / OpenAI)
  - [ ] 拍板:三阶段衔接方案 A / B(或者明确"先 A 再看")
- [ ] 通读 `graph.md`——State 和 Node 清单有没有缺漏
- [ ] 生成一份最终的 `.env` 模板和依赖清单(`pyproject.toml` / `requirements.txt`)

**退出条件**:上面的 TODO 全部勾掉,且所有 doc 里的 `TBD` 都有答案。

---

### M1 · Refine graph 可跑

**目标**:一个命令,输入一个 `raw_idea`,输出 `refined_idea`。Explorer ↔ Critic 对抗能跑通。

**范围**:
- [ ] 项目骨架(`pyproject.toml`、`maars/` 目录、`cli.py` 入口)
- [ ] `RefineState` TypedDict 定义
- [ ] `explorer` node(`create_react_agent` + web search tool)
- [ ] `critic` node(纯 LLM judge,返回 structured issues)
- [ ] Refine `StateGraph` 编译,接 `SqliteSaver` checkpointer
- [ ] CLI 入口:`maars refine "我想研究 ..."`,流式打印 Explorer / Critic 的对话
- [ ] Resume 测试:中途 Ctrl-C,`--resume <thread_id>` 能接着跑

**验证**:
- 至少跑通 3 个不同的 `raw_idea`,观察迭代是否收敛
- 观察 LangGraph 的 stream 事件,决定要不要在 M2 加 adapter

**退出条件**:`raw_idea` → `refined_idea` 端到端跑通,checkpoint 可以 resume。

---

### M2 · Write graph 可跑(独立)

**目标**:给定一个 `refined_idea` + 一个假的 `artifacts_dir`(手动构造的实验结果),跑 Writer ↔ Reviewer 对抗,输出 `paper.md`。

**范围**:
- [ ] `WriteState` 定义(大部分复用 Refine 的模式)
- [ ] `writer` node(要能读 `artifacts_dir` 里的文件)
- [ ] `reviewer` node(学术评审视角的 prompt)
- [ ] CLI:`maars write --idea <path> --artifacts <dir>`

**为什么独立跑**:Research 还没实现,所以 `artifacts_dir` 先手动构造(比如塞一个假的 `results.md` 和一张图)。这能让我们在不实现 Research 的前提下验证 Write 的完整链路。

**退出条件**:给定假 artifacts 能产出一篇完整的 paper.md,Reviewer 能推动至少 2 轮修订。

---

### M3 · Research graph 简化版

**目标**:跑通 Research,但不开并行、不做 re-decompose、不做 strategy loop。

**范围**:
- [ ] `ResearchState` 定义
- [ ] `calibrate` / `strategy` / `decompose`(单轮,不循环)
- [ ] `execute` **串行**版本(for loop,不用 Send)
- [ ] `verify` 只做 retry,不做 re-decompose
- [ ] `evaluate` 只打分,不循环回 strategy
- [ ] 代码执行 tool:**本地 subprocess**,不做 Docker 沙箱

**刻意省略的东西**:
- ❌ `Send` 并行(M4 再加)
- ❌ `re-decompose` 分支(M4)
- ❌ `strategy_update` 循环(M4)
- ❌ Docker 沙箱(M4 或更晚)

**退出条件**:一个简单研究想法 → 一组实验结果,虽然串行慢但跑通。

---

### M4 · Research graph 完整版

**目标**:加回 M3 省略的东西。

- [ ] `Send` API 并行 execute
- [ ] `task_results` 的 dict-merge reducer
- [ ] `verify` 的 re-decompose 分支
- [ ] `evaluate` 的 strategy_update 循环
- [ ] Docker 沙箱(如果决定做)

**退出条件**:能跑 5+ 原子任务的研究目标,并行正确 fan-in,strategy 能自动调整。

---

### M5 · 端到端三阶段串联

**目标**:`maars run "想法"` → paper.md,全自动。

**决策**:在这之前必须定 [`architecture.md §4`](architecture.md#4-未决问题) 的"三阶段衔接"方案 A / B。

- [ ] 顶层 orchestrator graph(或文件衔接方案)
- [ ] 端到端的 CLI 入口
- [ ] 端到端 checkpoint + resume
- [ ] 至少 1 个完整的端到端跑通案例存档

**退出条件**:完整 pipeline 能跑通且结果像样。

---

### M6+ · 可选增强

不是 MVP 必须,按需启用:
- [ ] 前端(FastAPI / LangServe / LangGraph Studio 三选一)
- [ ] 多 model provider 按阶段差异化
- [ ] Human-in-the-loop interrupt 点
- [ ] 英文文档和多语言 prompt
- [ ] 发布和文档站

## 2. 不做什么(明确排除)

这一节比"要做什么"更重要——防止范围蔓延。

| 不做 | 理由 |
|---|---|
| **多语言文档**(中英双语) | 原 MAARS 的翻译维护成本很重,MVP 阶段只维护中文 |
| **前端**(MVP 阶段) | 前端是原 MAARS 最重的包袱,LangGraph stream 在 CLI 下完全够观察 |
| **继承 `IterationState`、`Stage` 等原架构接口** | 换 LangGraph 的意义就是不用自建 runtime,继承这些会半途而废 |
| **继承 SSE label level 2/3/4 协议** | LangGraph 的 event 自带层级信息,不需要手打 tag |
| **继承 `round_N.md` 文件命名** | checkpoint 的 time-travel 提供天然的版本机制 |
| **Agno 框架** | 要纯粹体验 LangGraph + LangChain,混用会让"顺手感"分不清来源 |
| **Docker 沙箱**(M3 之前) | M3 用本地 subprocess 先跑通,沙箱是 M4 才考虑的隔离问题 |
| **发版、Release Notes、CHANGELOG** | 发版机制等 M5 后再考虑 |

## 3. 时间感(非承诺)

这不是承诺,是"如果一切顺利"的估计:

| 里程碑 | 估计工作量 | 备注 |
|---|---|---|
| M0 设计对齐 | 0.5-1 天 | 主要是通读和拍板 |
| M1 Refine | 2-3 天 | 第一次写 LangGraph,学习成本主要在这里 |
| M2 Write | 1-2 天 | 结构对称 Refine,快 |
| M3 Research 简化 | 3-4 天 | Node 多,但没并行/循环,可控 |
| M4 Research 完整 | 3-5 天 | `Send` + reducer + 多条件边,LangGraph 最难的部分 |
| M5 端到端 | 1-2 天 | 串联 + 调试 |

**粗略总计:2-3 周出可用 v1**。

---

<!-- TODO: 每个 milestone 开始前,把对应章节的 checklist 拉出来建一个 issue 或 task list。 -->
<!-- TODO: M0 的拍板项完成后,把"TBD"全部替换成明确决策。 -->
