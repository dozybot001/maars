# MAARS

中文 | [English](README.md)

**多智能体自动化研究系统** — 从一个想法到一篇完整论文，全自动。

MAARS 是一个混合式多智能体研究系统。给它一个研究想法或一个 Kaggle 比赛链接，它会自动精炼问题、分解为可执行任务、在 Docker 沙箱中运行实验、基于结果迭代改进，最终产出一篇完整论文。

## 效果展示

输入一个想法，看它自主完成研究：

```
"对比不同刚性特征下的 ODE 数值求解器 ——
 对显式方法与隐式方法的效率-精度权衡做系统性基准测试"
```

MAARS 会自动：搜索文献 → 确定方法论 → 编写并执行基准测试代码 → 生成图表 → 评估结果 → 迭代改进 → 撰写带嵌入图表的完整论文。

## 架构

### 数据流

```mermaid
flowchart LR
    IN["研究想法\n或 Kaggle 链接"] --> REF

    REF["① 精炼\nTeam: Explorer + Critic"]
    RES["② 研究\nAgentic Workflow"]
    WRI["③ 写作\nTeam: Writer + Reviewer"]

    REF -- "refined_idea.md" --> RES -- "tasks/ · artifacts/" --> WRI -- "paper.md" --> OUT["完整\n论文"]

    DB[(Session DB)]
    REF & RES & WRI <-.-> DB
```

### 系统架构

```mermaid
flowchart TB
    UI["前端 UI · SSE"] --> API["FastAPI → 编排器"]

    API --> REF["① 精炼\nTeam: Explorer + Critic"]
    API --> RES["② 研究\nAgentic Workflow"]
    API --> WRI["③ 写作\nTeam: Writer + Reviewer"]

    REF -- "refined_idea.md" --> DB
    RES -- "tasks/ · artifacts/" --> DB
    WRI -- "paper.md" --> DB
    DB[(Session DB\nresults/id/)]

    REF & RES & WRI --> AGNO["Agno · Google · Anthropic · OpenAI\nSearch · arXiv · Docker 沙箱"]
```

核心设计原则：**确定性控制交给 runtime，开放性执行交给 agent。**

MAARS 是一个**混合式多智能体系统**：精炼和写作阶段使用 Agno Team coordinate 模式（多 agent 协作），研究阶段使用 runtime 驱动的 agentic workflow。三个阶段仅通过文件型会话 DB 通信——完全解耦。

如果用 [harness engineering](https://openai.com/index/harness-engineering/)（OpenAI, 2026）的视角来看，MAARS 做的是同一类工作 — 状态外化、工具边界、验证回路、反馈循环 — 但作用在 **research-task 级别**，而非 OpenAI 所描述的 repo 级别。

| 阶段 | 模式 | 做什么 |
|------|------|-------|
| **精炼** | Multi-Agent Team | Explorer 调研文献 + Critic 质疑新颖性/可行性 → 精炼后的研究方案 |
| **研究** | Agentic Workflow | Runtime 控制：校准 → 策略 → 分解 → 执行 → 验证 → 评估 → 重规划 |
| **写作** | Multi-Agent Team | Writer 写初稿 + Reviewer 审稿反馈 → 修订后的论文 |

## 研究流水线详解

Research 阶段是核心工作引擎，以 **agentic workflow runtime** 形式运行，带反馈回路：

```
refined_idea.md
  ↓
校准    → Agent 评估当前领域"原子任务"的粒度边界
策略    → Agent 调研最佳方法、技术路线、基准线
分解    → 递归拆解为带依赖关系的原子任务 DAG
  ↓
┌─ 执行  → 按拓扑序分批运行（可并行）
│  验证  → 逐任务评分：通过 / 失败重试 / 重新分解
│  评估  → 跨迭代比较分数，判断是否改进停滞
│  重规划 → 根据评估反馈追加新任务
└─ 循环直到：迭代上限 或 分数停滞（<0.5% 改进）
  ↓
任务产出 + 实验产物 → 交给写作阶段
```

核心能力：
- **Docker 沙箱执行** — 真实代码在隔离容器中运行，预装 ML 工具栈
- **DAG 调度** — 任务按依赖顺序执行，安全时并行化
- **自动重分解** — 任务过于复杂时自动拆分为子任务
- **带评分的迭代** — 跨轮次跟踪 `best_score.json`，改进停滞时自动停止
- **断点续跑** — 可以中途暂停，稍后恢复，所有状态完整保留

## Kaggle 模式

直接粘贴 Kaggle 比赛链接：

```
https://www.kaggle.com/competitions/titanic
```

MAARS 会自动：拉取比赛元数据 → 下载数据集 → 构建上下文丰富的研究方案 → 跳过精炼阶段 → 直接进入研究阶段，数据挂载在 `/workspace/data/`。

## 快速开始

### 一键启动（推荐）

```bash
# Windows — 双击 start.bat，或命令行：
start.bat

# Linux / macOS / Git Bash：
bash start.sh
```

脚本自动完成：安装依赖、检查 `.env`、构建 Docker 镜像、启动服务、打开浏览器。

### 手动启动

```bash
git clone https://github.com/anthropics/MAARS.git && cd MAARS
pip install -r requirements.txt
cp .env.example .env          # 填入 API key
docker build -f Dockerfile.sandbox -t maars-sandbox:latest .   # 可选，用于代码执行
uvicorn backend.main:app --host 0.0.0.0 --port 8000
# 打开 http://localhost:8000
```

## 配置

所有配置项使用 `MAARS_` 前缀。将 `.env.example` 复制为 `.env` 后配置：

```env
# 选择 provider：google（默认）、anthropic 或 openai
MAARS_MODEL_PROVIDER=google

# 只需填写当前 provider 的 key
MAARS_GOOGLE_API_KEY=your-key
MAARS_GOOGLE_MODEL=gemini-2.5-flash

# MAARS_ANTHROPIC_API_KEY=your-key
# MAARS_ANTHROPIC_MODEL=claude-sonnet-4-5-20250514

# MAARS_OPENAI_API_KEY=your-key
# MAARS_OPENAI_MODEL=gpt-4o
```

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `MAARS_MODEL_PROVIDER` | `google` | LLM 提供商：`google`、`anthropic` 或 `openai` |
| `MAARS_RESEARCH_MAX_ITERATIONS` | `3` | 最大评估迭代轮数（1 = 不迭代） |
| `MAARS_DOCKER_SANDBOX_TIMEOUT` | `600` | 单容器超时时间（秒） |
| `MAARS_DOCKER_SANDBOX_MEMORY` | `4g` | 单容器内存限制 |
| `MAARS_DOCKER_SANDBOX_CONCURRENCY` | `2` | 最大并行容器数（即并行任务数） |
| `MAARS_KAGGLE_API_TOKEN` | — | Kaggle API token（或使用 `~/.kaggle/kaggle.json`） |

## 产出结构

每次运行创建带时间戳的会话文件夹：

```
results/{timestamp}-{slug}/
├── idea.md                  # 原始输入
├── refined_idea.md          # 精炼后的研究方案
├── calibration.md           # 原子任务定义
├── strategy.md              # 研究策略
├── plan_list.json           # 扁平任务列表（执行视图）
├── plan_tree.json           # 层级分解树
├── tasks/                   # 各任务输出（markdown）
├── artifacts/               # 代码脚本、图表、CSV、模型
│   ├── {task_id}/           # 每任务工作目录
│   └── best_score.json      # 全局最佳分数追踪
├── evaluations/             # 迭代评估结果
│   ├── eval_v0.json
│   └── eval_v1.json
├── paper.md                 # 最终论文
└── reproduce/               # 自动生成的复现文件
    ├── Dockerfile
    ├── run.sh
    └── docker-compose.yml
```

## 前端

Web UI 通过 SSE 提供实时观测：

- **进度条** — 7 阶段流水线可视化（精炼 → 校准 → 策略 → 分解 → 执行 → 评估 → 写作）
- **命令面板** (Ctrl+K) — 启动、暂停、恢复流水线
- **推理日志** — 实时流式展示 LLM 推理过程、工具调用和返回结果
- **过程查看器** — 任务树、执行批次、产物、文档
- **Docker 状态** — 沙箱连接指示器

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | FastAPI, Python async |
| Agent 框架 | Agno（Team coordinate 模式 + 单 Client workflow） |
| LLM 提供商 | Google Gemini, Anthropic Claude, OpenAI GPT |
| 代码执行 | Docker 容器（Python 3.12 + ML 工具栈） |
| 前端 | 原生 JS, SSE, 无构建步骤 |
| 存储 | 文件型会话 DB |
| 搜索工具 | DuckDuckGo, arXiv, Wikipedia |

## 文档

| 文档 | 内容 |
|------|------|
| [架构设计](docs/CN/architecture.md) | 系统设计理念与演进策略 |

## 社区

[贡献指南](.github/CONTRIBUTING.md) · [行为准则](.github/CODE_OF_CONDUCT.md) · [安全策略](.github/SECURITY.md)

## 许可证

MIT
