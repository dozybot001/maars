# MAARS

中文 | [English](README.md)

**多智能体自动化研究系统** — 从一个想法到一篇完整论文，全自动。

## 它做什么

输入一个研究想法，MAARS 通过 4 阶段管线自动生成结构化论文：

```
想法 → 精炼 → 规划 → 执行 → 写作 → 论文
```

每个阶段由 LLM 调用或自主 Agent 驱动。系统将想法分解为原子任务，按依赖关系并行执行（含验证），最终综合为学术论文。

## 三种模式

| 模式 | 工作方式 | 适用场景 |
|------|---------|---------|
| **Mock** | 回放录制的 LLM 输出 | 开发、UI 测试 |
| **Gemini** | 直接调用 Google Gemini API | 快速、结构化的 LLM 管线 |
| **Agent** | Google ADK Agent + ReAct 循环 | 自主推理 + 工具调用 |

`.env` 一行切换：

```env
MAARS_LLM_MODE=mock      # 或 gemini，或 agent
MAARS_GOOGLE_API_KEY=your-key
```

## 架构

```
前端 (Vanilla JS)               后端 (FastAPI)
┌─────────────────────┐       ┌──────────────────────────────┐
│ 输入框 + 4 阶段卡片   │       │ pipeline/                    │
│ LLM 输出日志 (左)     │◄─SSE──│   stage.py    (BaseStage)    │
│ 过程与产出 (右)       │       │   orchestrator.py            │
└─────────────────────┘       │   refine.py / plan.py        │
                               │   execute.py / write.py      │
                               ├──────────────────────────────┤
                               │ llm/          (LLMClient ABC)│
                               ├──────────────────────────────┤
                               │ mock/    gemini/    agent/    │
                               │ (模式层 — 配置切换)            │
                               └──────────────────────────────┘
```

**核心设计决策：**
- **`llm/` → `pipeline/` → `mode/`**：三层解耦，管线层完全不知道当前运行哪种模式
- **统一 `call_id` 流式模型**：每次 LLM 调用（顺序或并行）发射带标记的 chunk，前端按 `call_id` 路由
- **字符串进，字符串出**：阶段间通过 `stage.output` 传递，无需共享记忆

## 管线阶段

### 精炼 (Refine)
3 轮：**探索** → **评估** → **结晶**。将模糊想法转化为结构化研究提案。

### 规划 (Plan)
递归分解为原子任务 + 依赖 DAG。并行批次处理。深度限制（默认 3 层）。依赖解析采用继承 + 展开算法。

### 执行 (Execute)
拓扑排序 → 并行批次执行 → 验证 → 可选重试。每个任务结果存入文件 DB。依赖任务的输出作为上下文注入。

### 写作 (Write)
大纲 → 逐章节写作 → 润色。每个章节只接收相关任务输出，保持 prompt 聚焦。

## 快速开始

```bash
git clone https://github.com/dozybot001/MAARS.git
cd MAARS
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 配置
cp .env.example .env  # 填入你的 API key

# 运行
uvicorn backend.main:app --host 0.0.0.0 --port 8000
# 打开 http://localhost:8000
```

## 前端

双栏工作区：
- **左侧**：LLM 输出日志 — 流式输出，阶段可折叠
- **右侧**：过程与产出 — 分解树、执行进度、精炼想法和论文的文件图标

零构建步骤。纯 HTML/CSS/JS + ES Modules。

## 文件 DB

每次研究运行创建带时间戳的文件夹：

```
research/20260323-210300-how-does-framing-effect-in/
├── idea.md              # 原始输入
├── refined_idea.md      # 精炼输出
├── plan.json            # 扁平原子任务列表
├── plan_tree.json       # 完整分解树
├── paper.md             # 最终论文
└── tasks/
    ├── 1_1.md           # 各任务输出
    ├── 1_2.md
    └── ...
```

## 展示

`showcase/` 中包含两次完整的研究运行：

| 运行 | 模式 | 主题 | 任务数 |
|------|------|------|-------|
| `20260323-210300-*` | Gemini | 认知缓冲假说 — 新闻框架效应的文化调节 | 31 |
| `20260323-223406-*` | Agent | HMAO — 对抗式多 Agent 角色专业化 | 12 |

MAARS 的构建语义历史现维护在 [Intent](https://github.com/dozybot001/Intent) 的官方 showcase 中：[`showcase/maars`](https://github.com/dozybot001/Intent/tree/main/showcase/maars)。其中包含 1 个 intent、8 个 snaps、3 个 decisions，覆盖了从架构设计到 Agent 模式接入的全过程。

## 社区

- [贡献指南](.github/CONTRIBUTING.md)
- [行为准则](.github/CODE_OF_CONDUCT.md)
- [安全策略](.github/SECURITY.md)

GitHub 中的 Issue 和 Pull Request 模板目前使用英文。

## 许可证

MIT
