# MAARS 架构（LangGraph 版）

> 这份文档讲**结构和技术选型**，不讲思想（见 [`concept.md`](concept.md)），也不讲具体的 graph 定义（见 [`graph.md`](graph.md)）。

## 1. 架构理念

**不变的分工**：runtime 管控制流（确定性），agent 管开放任务（LLM）。见 [`concept.md`](concept.md#21-runtime-管控制流agent-管开放任务)。

**变化的实现**：

| 层 | 原 MAARS (v13.4.0-agno) | LangGraph 版 |
|---|---|---|
| 编排层 | 手写 `Stage` / `TeamStage` 基类 + `IterationState` | LangGraph `StateGraph` + `Conditional Edge` |
| Agent 层 | Agno 框架 | LangChain Core + Gemini 内置能力 |
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

### 2.2 Agent / Tool：LangChain Core + Gemini 内置能力

- **基础 model 类**：直接用 `langchain_google_genai.ChatGoogleGenerativeAI`，不经过 `init_chat_model()` 的 provider 路由层。
- **Explorer 的搜索能力**：用 Gemini 内置的 `google_search` grounding，通过 `model.bind_tools([{"google_search": {}}])` 开启。Explorer 不用 `create_react_agent`，而是直接 `.invoke()`——grounding 在 one-shot 调用里由模型自主决定要不要搜，不经过显式的 ReAct thought/action/observation 循环。
- **Critic / Reviewer 的结构化输出**：`model.with_structured_output(PydanticSchema)`，在 Gemini 3 上已验证稳定（见 §2.3 的 Step 3 验证结论）。

**刻意砍掉的东西**（维持最小开发面）：

- ❌ `langchain` meta-package + `init_chat_model()` 抽象层——只有 Gemini，不需要 provider 路由
- ❌ `langchain-anthropic`、`langchain-tavily`——不支持多 provider，不需要外部 search
- ❌ `create_react_agent`——Explorer 一次 invoke + grounding 就够，不走 ReAct loop
- ❌ 自定义 `@tool` / `BaseTool`——没有外部 tool

**代价**：Explorer 和项目整体都绑定 Gemini provider。将来要切 Claude / OpenAI，Explorer 需要重新引入外部 search tool（比如 Tavily）+ `create_react_agent`。这是一个**有意识的 trade-off**——MVP 阶段选择简单性 > 通用性。

### 2.3 Model Provider

**Gemini only** — 默认 `gemini-3-flash-preview`，可通过 `MAARS_CHAT_MODEL` 环境变量 override 到其它 Gemini 模型（如 `gemini-3-pro`）。

**选型演变**：

- **2026-04-11** 最初拍板 Anthropic Claude，理由是对抗 + 判断最强、structured output 最稳定
- **2026-04-12 上午** 切换到 Gemini-default + multi-provider 抽象：Anthropic 账户余额为 0 成为 Step 2 blocker，手头有 Gemini 余额
- **2026-04-12 下午** 砍掉 multi-provider 抽象，回到 Gemini-only：Step 3 验证证明 Gemini 3 的 structured output 足够稳定，且 Gemini 内置 `google_search` grounding 省掉 Tavily 依赖。**维持最小开发面 > 保留 provider 切换能力**

**Step 3 在 Gemini 3 Flash Preview 下的 structured output 验证结论**：

- 中文 prompt + Pydantic schema 完全稳定，无 JSON 格式漂移
- Critic 的 issue id 规则严格遵守，severity 分层合理
- `passed` 路径和 fail 路径都能正确触发
- 方法论审查深度足够（观察到 2x2 因子实验的隐性自变量 insight）

**将来重新引入 multi-provider 的条件**：

- M3 Research 跑通后，若某个 node 在 Gemini 上表现明显差于其它 provider
- 或 M5 之后，做 end-to-end 的 benchmark 比较

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
src/maars/
├── config.py              # 环境变量、常量、路径
├── state.py               # RefineState、Issue 等类型
├── models.py              # get_chat_model / get_search_model 工厂
├── cli.py                 # typer 入口
├── prompts/
│   ├── explorer.py        # Explorer system prompt
│   ├── critic.py          # Critic system prompt
│   └── ...                # 未来的 writer / reviewer / research 相关
├── agents/
│   ├── explorer.py        # draft_proposal() 函数
│   ├── critic.py          # CritiqueResult + critique_draft() 函数
│   └── ...
└── graphs/                # （M1 Step 5 创建）
    └── refine.py          # Refine StateGraph 编译
```

**没有的目录**（相对早期草稿）：

- `tools/` — 没有外部 tool，Gemini grounding 内置，所以不需要这个目录
- `research/`、`write/` 先不建，M2 / M3 再加

## 4. 未决问题

| 问题 | 选项 | 优先级 |
|---|---|---|
| 三阶段衔接方式 | (a) 顶层 orchestrator graph,状态一路传下去 / (b) 三个独立 graph,通过文件衔接 | 高,影响 state 设计 |
| Research 的代码执行沙箱 | (a) 本地 subprocess / (b) Docker / (c) 外部服务 | 中,MVP 可以先本地 |
| Checkpointer 存储位置 | (a) 单个 SQLite 文件 / (b) 按 session 一个文件 | 低 |
| Model provider 选型 | ✅ **已定:Gemini only** (`gemini-3-flash-preview`) | 2026-04-12 简化 |
| Research 并行度 | (a) 串行 / (b) `Send` 并行 | 中,MVP 可以先串行 |
| Human-in-the-loop | 预留 `interrupt` 点 / 完全不做 | 低,MVP 不做 |

---

<!-- TODO: §3 的模块划分等 graph.md 的 Refine 图定稿后再修正 -->
