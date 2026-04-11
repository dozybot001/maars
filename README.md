<p align="center">
  <h1 align="center">MAARS</h1>
  <p align="center"><b>多智能体自动化研究系统 · LangGraph 版</b></p>
  <p align="center">从研究想法到完整论文——全自动、端到端。</p>
</p>

---

## 项目状态

> **doc-first, no code yet** — 当前分支从零开始用 LangGraph 重写，正在对齐设计，尚未开始编码。

MAARS 的目标不变：接受一个模糊的研究想法（或 Kaggle 比赛链接），通过三阶段流水线 **Refine → Research → Write** 产出结构化研究产物和完整的 `paper.md`，全程自主运行、迭代自我改进。

**这次重写只换实现，不换思想。** 沿用原 MAARS 的三阶段分工、迭代对抗循环、分解验证循环——把编排层从手写 runtime 换成 LangGraph 原生的 `StateGraph`，以体验 LangGraph 做 Agent 编排的心智模型。

## 历史

| 版本 | 状态 | 说明 |
|---|---|---|
| [`v13.4.0-agno`](../../releases/tag/v13.4.0-agno) | 冻结快照 | 基于 [Agno](https://github.com/agno-agi/agno) + 手写 `Stage` runtime 的最终版本，位于 `main` 分支 |
| `langgraph`（当前） | 开发中 | 基于 LangGraph + LangChain 的重写版本，从零开始 |

## 文档

> 当前只有设计文档，代码尚未动工。阅读顺序建议：

1. [`docs/concept.md`](docs/concept.md) — 核心思想（继承自原 MAARS）：三阶段、迭代对抗、分解验证
2. [`docs/architecture.md`](docs/architecture.md) — LangGraph 视角的架构：StateGraph、Checkpointer、Stream
3. [`docs/graph.md`](docs/graph.md) — 三阶段的 graph 结构、State schema、Node/Edge 定义
4. [`docs/roadmap.md`](docs/roadmap.md) — MVP 范围、里程碑、"不做什么"清单

历史设计文档保留在 [`docs/archive/`](docs/archive/) 下，作为先辈经验参考，不作为当前文档。

## 技术栈（计划）

- **编排**：[LangGraph](https://github.com/langchain-ai/langgraph)
- **Agent / Tool**：[LangChain](https://github.com/langchain-ai/langchain)（`create_react_agent` + `@tool`）
- **Checkpointer**：LangGraph 官方 SQLite saver
- **Model Provider**：TBD
- **入口形态**：TBD（CLI / FastAPI / LangServe / LangGraph Studio）

详见 [`docs/architecture.md`](docs/architecture.md)。

## License

[MIT](LICENSE)
