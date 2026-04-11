<p align="center">
  <h1 align="center">MAARS</h1>
  <p align="center"><b>多智能体自动化研究系统 · LangGraph 版</b></p>
  <p align="center">从研究想法到完整论文——全自动、端到端。</p>
</p>

---

## 项目状态

> **M1 Refine 可跑**（Explorer ↔ Critic 对抗循环端到端工作）。**M2 Write 暂停**，M3 Research 未开始。

MAARS 的目标：接受一个模糊的研究想法，通过三阶段流水线 **Refine → Research → Write** 产出结构化研究产物和完整的论文，全程自主运行、迭代自我改进。

当前 `langgraph` 分支聚焦在 **Refine 阶段**——先把 Explorer / Critic 的迭代打磨好，再往后推。M2 Write 实现曾在 commit `06584f3` 验证过（4 轮收敛到 `passed=True`），但为了简化 scope 暂时砍掉，待 Refine 稳定后再重启。

**这次重写只换实现，不换思想**——沿用原 MAARS 的迭代对抗循环思想，把编排层从手写 runtime 换成 LangGraph 原生 `StateGraph`。

## 快速开始

**环境要求**：Python 3.11+、[uv](https://docs.astral.sh/uv/) 0.11+、Google Gemini API key

```bash
git clone -b langgraph https://github.com/dozybot001/MAARS.git
cd MAARS
cp .env.example .env
# 编辑 .env，填入 GOOGLE_API_KEY (从 https://aistudio.google.com/apikey 获取)
uv sync
uv run maars --help
```

## 使用

### Refine — 把模糊想法精炼成可执行的研究目标

```bash
# 最简：每次自动新开一个 thread（第一次是 refine-001）
uv run maars refine "研究大模型推理能力"

# 长 idea 从文件读
uv run maars refine --from-file examples/test_ideas/speculative_decoding.md

# Resume 一个中断的 thread（thread id 从上次输出最后一行复制）
uv run maars refine --thread refine-003
```

**Session 输出**：每次 run 产生一个独立目录 `data/refine/{NNN}/`，包含：

- `raw_idea.md` — 原始输入
- `draft.md` — 最终 refined draft
- `issues.json` — 剩余 issues（结构化）
- `meta.json` — 元数据（轮次、passed、模型、时间）

运行过程中 Explorer / Critic 每轮状态实时流式打印，最终 draft 在 Rich Panel 里完整展示。

## 命令参考

| 命令 | 说明 |
|---|---|
| `maars refine <idea>` / `maars refine --from-file <file>` | Refine graph — Explorer ↔ Critic 迭代 |
| `maars hello` | CLI wiring smoke test |
| `maars sanity` | (debug) 单次调用 chat model 验证 API + key |
| `maars draft <idea>` | (debug) 只跑 Explorer 一次 |
| `maars critique <draft>` | (debug) 只跑 Critic 一次 |

`maars refine` 默认**每次自动分配新 thread id**（`refine-001` / `refine-002` / ...）。只有用 `--thread <id>` 显式指定才进入 resume 语义。

**完整命令参考**（含 session 文件组织、FAQ、debug checklist）：[`docs/cli.md`](docs/cli.md)

## 环境变量

所有配置通过 env 变量调整，长期配置写进 `.env`。

| 变量 | 默认 | 说明 |
|---|---|---|
| `GOOGLE_API_KEY` | — | **必填**，Gemini API key |
| `MAARS_CHAT_MODEL` | `gemini-3-flash-preview` | Gemini 模型 ID |
| `MAARS_REFINE_MAX_ROUND` | `5` | Refine 最大迭代轮次 |

## 架构简述

- **编排层**：LangGraph `StateGraph` + async streaming + `AsyncSqliteSaver` checkpointer
- **Agent 层**：直接用 `ChatGoogleGenerativeAI`；Explorer 用 Gemini 内置 `google_search` grounding；Critic 用 `with_structured_output()` 返回 Pydantic `CritiqueFeedback`
- **State**：`TypedDict` + 选择性 reducer（`issues` 由 Python 代码覆盖维护，`resolved` 通过 `operator.add` 累积）
- **Feedback 语义**：**增量**（incremental）——Critic 只返回 `resolved + new_issues`，`critic_node` 用 `next = (prior - resolved) + new_issues` 合并，`passed` 由 Python 规则判断（0 blocker + ≤1 major）。这个设计对齐原 MAARS 的 IterationState
- **CLI**：typer + rich，streaming via `graph.astream_events(version="v2")`

详细设计文档：

1. [`docs/concept.md`](docs/concept.md) — 核心思想
2. [`docs/architecture.md`](docs/architecture.md) — 技术栈、模块划分
3. [`docs/graph.md`](docs/graph.md) — Graph / State / Node / Edge 定义
4. [`docs/roadmap.md`](docs/roadmap.md) — 里程碑
5. [`docs/cli.md`](docs/cli.md) — CLI 完整参考

历史设计文档归档在 [`docs/archive/`](docs/archive/)。

## 历史

| 版本 | 状态 | 说明 |
|---|---|---|
| [`v13.4.6`](../../releases/tag/v13.4.6) | 冻结快照 | 基于 [Agno](https://github.com/agno-agi/agno) + 手写 `Stage` runtime 的最终版本，位于 `main` 分支 |
| `langgraph`（当前） | 开发中 | 基于 LangGraph 的重写版本，当前聚焦 M1 Refine |

## License

[MIT](LICENSE)
