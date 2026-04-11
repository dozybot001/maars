<p align="center">
  <h1 align="center">MAARS</h1>
  <p align="center"><b>多智能体自动化研究系统 · LangGraph 版</b></p>
  <p align="center">从研究想法到完整论文——全自动、端到端。</p>
</p>

---

## 项目状态

> **M1 + M2 完成** — Refine graph 和 Write graph 都可端到端跑通。M3 Research graph 尚未开始。

MAARS 的目标：接受一个模糊的研究想法（或 Kaggle 比赛链接），通过三阶段流水线 **Refine → Research → Write** 产出结构化研究产物和完整的 `paper.md`，全程自主运行、迭代自我改进。

当前 `langgraph` 分支实现了 **Refine**（Explorer ↔ Critic 对抗循环）和 **Write**（Writer ↔ Reviewer 对抗循环），Research 会在 M3 加入。

**这次重写只换实现，不换思想**。沿用原 MAARS 的三阶段分工、迭代对抗循环、分解验证循环——把编排层从手写 runtime 换成 LangGraph 原生 `StateGraph`。

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
# 短 idea 用 positional argument
uv run maars refine "研究大模型推理能力"

# 长 idea 从文件读
uv run maars refine --from-file my_idea.md

# 自定义 thread id（用于 checkpoint + resume）
uv run maars refine "..." --thread exp1

# Resume：同 thread id 再次运行会从最后一次 checkpoint 继续
uv run maars refine "..." --thread exp1

# 强制新建（忽略同 thread id 已有的 checkpoint）
uv run maars refine "..." --thread exp1 --fresh
```

**输出**：最终 refined idea 保存到 `data/ideas/{thread_id}.md`。运行过程中 Explorer / Critic 每轮状态会实时流式打印，最终 draft 在一个 Rich Panel 里完整展示。

### Write — 从 refined idea + artifacts 生成论文

```bash
# 基本用法
uv run maars write <refined_idea.md> <artifacts_dir/> --thread w1

# 用自带的 example fake artifacts（GSM8K PRM search 的假数据）
uv run maars write examples/fake_artifacts/refined_idea.md examples/fake_artifacts --thread w1

# Resume
uv run maars write <idea.md> <artifacts_dir/> --thread w1
```

**输出**：最终 paper 保存到 `data/papers/{thread_id}.md`。`artifacts_dir` 下所有 `*.md` 文件（递归）会被读取作为 experiment context。

## 命令参考

| 命令 | 说明 |
|---|---|
| `maars refine <idea>` / `maars refine --from-file <file>` | Refine graph — Explorer ↔ Critic 迭代 |
| `maars write <idea.md> <artifacts/>` | Write graph — Writer ↔ Reviewer 迭代 |
| `maars hello` | CLI wiring smoke test |
| `maars sanity` | (debug) 单次调用 chat model 验证 API + key |
| `maars draft <idea>` | (debug) 只跑 Explorer 一次（不迭代） |
| `maars critique <draft>` | (debug) 只跑 Critic 一次（不迭代） |

Graph 命令（`refine` / `write`）都支持：

- `--thread <id>` — checkpointing + resume key
- `--fresh` — 忽略同 thread 的已有 checkpoint，强制新建

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `GOOGLE_API_KEY` | — | **必填**，Gemini API key |
| `MAARS_CHAT_MODEL` | `gemini-3-flash-preview` | Gemini 模型 ID |
| `MAARS_REFINE_MAX_ROUND` | `5` | Refine 最多迭代轮次 |
| `MAARS_WRITE_MAX_ROUND` | `5` | Write 最多迭代轮次 |

## 架构简述

- **编排层**：LangGraph `StateGraph` + async streaming + `AsyncSqliteSaver` checkpointer
- **Agent 层**：直接用 `ChatGoogleGenerativeAI`；Explorer / Writer 用 Gemini 内置 `google_search` grounding，Critic / Reviewer 用 `with_structured_output()` 返回 Pydantic `CritiqueResult` / `ReviewResult`
- **State**：`TypedDict` + 选择性 reducer（`issues` overwrite，`resolved` accumulate via `operator.add`）
- **CLI**：typer + rich，streaming via `graph.astream_events(version="v2")`

详细设计文档：

1. [`docs/concept.md`](docs/concept.md) — 核心思想（三阶段、迭代对抗、分解验证）
2. [`docs/architecture.md`](docs/architecture.md) — 技术栈、模块划分、决策点
3. [`docs/graph.md`](docs/graph.md) — 每个 graph 的 State / Node / Edge 定义
4. [`docs/roadmap.md`](docs/roadmap.md) — M0~M6 里程碑、"不做什么"清单

历史设计文档归档在 [`docs/archive/`](docs/archive/)。

## 历史

| 版本 | 状态 | 说明 |
|---|---|---|
| [`v13.4.6`](../../releases/tag/v13.4.6) | 冻结快照 | 基于 [Agno](https://github.com/agno-agi/agno) + 手写 `Stage` runtime 的最终版本，位于 `main` 分支 |
| `langgraph`（当前） | 开发中 | 基于 LangGraph + LangChain 的重写版本 |

## License

[MIT](LICENSE)
