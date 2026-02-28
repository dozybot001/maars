# MAARS

Multi-Agent Automated Research System（多智能体自动研究系统）

## 快速开始

**前置**：已安装 [Python 3.10+](https://www.python.org/downloads/) 并勾选 “Add Python to PATH”。

```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn main:asgi_app --host 0.0.0.0 --port 3001 --loop asyncio --http h11
```

在浏览器中访问 **http://localhost:3001**

点击 **Load Example Idea** 可加载示例 idea。

## 核心流程

### 1. Generate Plan（规划）

用户输入 idea → Planner 递归分解为任务树 → 保存 `plan.json`

- **Atomicity**：判断任务是否可直接执行（原子任务）
- **Decompose**：非原子任务分解为 2–6 个子任务，仅同级依赖
- **Format**：为原子任务生成 input/output 规范

### 2. Generate Map（执行图）

从 plan 提取原子任务 → 解析依赖（继承+下沉）→ 拓扑排序分 stage → 保存 `execution.json`

### 3. Execution（执行）

Executor 池并行执行就绪任务，每个任务执行后 Validate，实时状态推送。

## Agent 工作流

**AI Mode** 可选 Mock / LLM / Agent。Agent 模式下，Planner 与 Executor 均采用 ReAct 式多轮工具调用。

### Planner Agent

多轮调用工具完成分解，可 LoadSkill 加载技能（分解模式、研究范围、格式规范等）：

| 工具 | 用途 |
|------|------|
| CheckAtomicity | 判断任务是否原子 |
| Decompose | 分解为非原子子任务 |
| FormatTask | 为原子任务生成 input/output |
| AddTasks / UpdateTask | 增改任务 |
| GetPlan / GetNextTask | 读取当前计划 |
| ListSkills / LoadSkill | 加载 Planner 技能 |

### Executor Agent

多轮调用工具完成任务，每个任务在独立沙箱中运行，可 LoadSkill 加载技能（markdown-reporter、json-utils 等）：

| 工具 | 用途 |
|------|------|
| ReadArtifact | 读取依赖任务输出 |
| ReadFile / WriteFile | 读写沙箱内文件 |
| ListSkills / LoadSkill | 加载 Executor 技能 |
| Finish | 提交任务输出 |

## 项目结构

```
maars/
├── backend/
│   ├── main.py          # FastAPI + Socket.io 入口
│   ├── api/             # 路由、schemas、state
│   ├── plan/            # 规划：atomicity → decompose → format（业务逻辑）
│   ├── visualization/   # 分解树、执行图布局
│   ├── execution/       # 执行：runner、execution、validation
│   ├── shared/          # 共享模块：graph、llm_client、skill_utils、utils
│   ├── db/              # 文件存储：db/{plan_id}/、settings.json
│   └── test/            # Mock AI
└── frontend/            # 静态页面、任务树、WebSocket
```

## 配置

按 **Alt+Shift+S** 打开 **Settings**：Theme、DB Operation（Restore/Clear）、AI Mode（Mock/LLM/Agent）、Preset（Base URL、API Key、Model）、模式参数（Temperature、最大轮数等）。

## 文档

- [前端脚本与模块依赖](docs/FRONTEND_SCRIPTS.md)
- [Release Note 标准](docs/RELEASE_NOTE_STANDARD.md)
- [执行图布局规则](backend/visualization/EXECUTION_LAYOUT_RULES.md)
