# MAARS 架构（LangGraph 版）

> 这份文档讲**结构和技术选型**，不讲思想（见 [`concept.md`](concept.md)），也不讲具体的 graph 定义（见 [`graph.md`](graph.md)）。

## 1. 架构理念

**不变的分工**：runtime 管控制流（确定性），agent 管开放任务（LLM）。见 [`concept.md`](concept.md#21-runtime-管控制流agent-管开放任务)。

**变化的实现**：

| 层 | 原 MAARS (v13.4.0-agno) | LangGraph 版 |
|---|---|---|
| 编排层 | 手写 `Stage` / `TeamStage` 基类 + `IterationState` | LangGraph `StateGraph` + `Conditional Edge` |
| Agent 层 | Agno 框架 | LangChain (`create_react_agent` + `@tool`) |
| 状态持久化 | 文件型 session DB（自建） | LangGraph Checkpointer + 少量 file side effect |
| Stream | 自定义 SSE (`_send` + label level 2/3/4) | `graph.astream_events(version="v2")` |
| 入口 | FastAPI + 前端三面板 | **TBD**（先 CLI，稳定后再议） |

**换 LangGraph 的动机不是"性能更好"，而是"心智模型更纯粹"**。原版的 `Stage + IterationState` 本质上是在手写 mini LangGraph——直接用上游框架可以省去维护自建 runtime 的成本，同时获得 checkpointer、stream、human-in-loop 等现成能力。

## 2. 技术栈

### 2.1 编排：LangGraph

- **核心抽象**：`StateGraph(State)` — 以 TypedDict 为状态、Node 为函数、Edge 为条件转移的状态机。
- **关键特性**：
  - `add_node` / `add_edge` / `add_conditional_edges` — graph 构建
  - `Send` API — fan-out 并行任务
  - `interrupt` — human-in-the-loop（预留，MVP 不用）
  - `compile(checkpointer=...)` — 编译成可运行对象

每个阶段（Refine / Research / Write）是一个独立的 `StateGraph`。三个阶段之间通过顶层 orchestrator graph 串联，或通过文件衔接（TBD，见 §4）。

### 2.2 Agent / Tool：LangChain

- **Agent 构造器**：`langgraph.prebuilt.create_react_agent` — 开箱即用的 ReAct agent，返回一个可作为 subgraph node 嵌入的 runnable。
- **Tool 定义**：`@tool` 装饰器，或继承 `BaseTool`。
- **为什么不用 Agno**：要纯粹体验 LangGraph + LangChain 的心智模型。混用会让 "顺手感" 分不清是哪边带来的。

**例外**：如果某些功能 LangChain 生态缺失而 Agno 有，允许局部引入，但要在 [`graph.md`](graph.md) 里显式记录为"例外"。

### 2.3 Model Provider

**TBD**。候选：
- Google Gemini（原 MAARS 在用，`gemini-2.5-pro` 带 search grounding）
- Anthropic Claude（强推理 + 长上下文）
- OpenAI GPT-4.1 / o 系列

决策点：
- Refine / Write 需要强对抗能力 → Claude 或 Gemini
- Research 的 Execute 需要代码 + tool use 能力 → 都行
- Verify / Evaluate 需要可靠的判断力 → 强模型

**建议先用一个 provider 跑通全流程，再决定要不要按阶段差异化**。

### 2.4 Checkpointer

**默认**：LangGraph 官方 `SqliteSaver`（或 `AsyncSqliteSaver`）。
- 存的是 State 快照，按 `thread_id` 组织
- 支持 resume、time-travel、branching

**与文件 side effect 的分工**：
- Checkpointer：轻量运行时状态（当前 round、当前 phase、迭代次数、评审 issues 列表等）
- 文件 side effect：重量级产物（paper.md、代码 artifacts、图表）— 由 node 内部直接写盘

**不继承原 MAARS 的 `round_N.md` 协议**。新架构下，产物的版本由 checkpoint 的 time-travel 能力自然提供，不需要显式的 `round_N` 命名。

### 2.5 Stream

**方式**：`graph.astream_events(version="v2")`,订阅所有 node 的事件。

**消费场景**:
- CLI 阶段（MVP）：直接 pretty-print 到 stdout
- 未来前端（如果做）：事件流经一层 adapter 转成自定义事件格式推给前端

**不继承原 MAARS 的 SSE label level 2/3/4**。LangGraph 的事件自带 `run_id` / `parent_ids` / `tags` / `metadata`，天然支持层级关系，不需要手动打标签。

### 2.6 入口形态

**MVP**：**CLI only**。一个命令，一个配置文件，一个输出目录。

**原因**：
- 前端是原 MAARS 最重的包袱之一
- LangGraph 的 stream 事件在 CLI 下就能完全观察
- 前端可以等后端 graph 稳定后再加

**未来候选**：
- FastAPI + 自建前端（继承原 MAARS 三面板）
- [LangServe](https://github.com/langchain-ai/langserve) — 官方 REST wrapper
- [LangGraph Studio](https://github.com/langchain-ai/langgraph-studio) — 官方可视化调试工具

## 3. 模块划分（初版草稿）

```
maars/
├── graphs/
│   ├── refine.py         # Refine StateGraph + Explorer/Critic nodes
│   ├── research.py       # Research StateGraph + Decompose/Execute/Verify/Evaluate
│   ├── write.py          # Write StateGraph + Writer/Reviewer nodes
│   └── orchestrator.py   # 顶层 graph,串联三阶段
├── agents/
│   ├── explorer.py       # create_react_agent 实例 + prompt
│   ├── critic.py
│   ├── writer.py
│   ├── reviewer.py
│   └── ...
├── tools/
│   ├── search.py         # web search tool
│   ├── code_exec.py      # 代码执行 tool
│   └── ...
├── state/
│   ├── refine_state.py   # TypedDict schemas
│   ├── research_state.py
│   └── write_state.py
├── prompts/
│   └── ...               # 纯中文 prompt,暂不做 i18n
├── cli.py                # 入口
└── config.py             # 模型、路径等配置
```

**这个划分会随着 graph 设计变化**,不是最终结构。先放这里作为"心里有个大概"。

## 4. 未决问题

| 问题 | 选项 | 优先级 |
|---|---|---|
| 三阶段衔接方式 | (a) 顶层 orchestrator graph,状态一路传下去 / (b) 三个独立 graph,通过文件衔接 | 高,影响 state 设计 |
| Research 的代码执行沙箱 | (a) 本地 subprocess / (b) Docker / (c) 外部服务 | 中,MVP 可以先本地 |
| Checkpointer 存储位置 | (a) 单个 SQLite 文件 / (b) 按 session 一个文件 | 低 |
| Model provider 选型 | Gemini / Claude / OpenAI | 高,跑通 Refine 之前必须定 |
| Research 并行度 | (a) 串行 / (b) `Send` 并行 | 中,MVP 可以先串行 |
| Human-in-the-loop | 预留 `interrupt` 点 / 完全不做 | 低,MVP 不做 |

---

<!-- TODO: §3 的模块划分等 graph.md 的 Refine 图定稿后再修正,现在是占位。 -->
<!-- TODO: §2.3 Model provider 选型,需要用户拍板后删掉"TBD"。 -->
<!-- TODO: §4 未决问题,每个都要有一条显式决策或默认选项。 -->
