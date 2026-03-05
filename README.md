# MAARS

Multi-Agent Automated Research System — 多智能体自动研究系统。从模糊 idea 到论文草稿的一站式研究流水线。

---

## 快速开始

**前置**：Python 3.10+

```bash
cd backend
pip install -r requirements.txt
uvicorn main:asgi_app --host 0.0.0.0 --port 3001 --loop asyncio --http h11
```

访问 <http://localhost:3001>。刷新页面会填充示例 idea。

---

## 使用流程

```text
输入 idea → Refine（可选）→ Plan → Execute → Write
```

| 步骤 | 按钮 | 作用 |
| --- | --- | --- |
| Refine | Refine | 提取关键词、arXiv 检索、生成 refined idea |
| Plan | Plan | 将 idea 分解为可执行任务树 |
| Execute | Execute | 执行原子任务、验证产出 |
| Write | Write | 根据 Plan 与 Task 产出生成论文草稿 |

Thinking 区域展示推理过程，Output 区域展示最终产出（文献、任务 artifact、论文）。

---

## 四 Agent

| Agent | 职责 |
| --- | --- |
| Idea | 关键词提取、arXiv 检索、Refined Idea |
| Plan | 任务分解（atomicity → decompose → format → quality） |
| Task | 原子任务执行与验证 |
| Paper | 论文草稿生成（Markdown/LaTeX） |

每个 Agent 支持 **Mock**（模拟）、**LLM**（单轮）、**Agent**（工具循环）三种模式。
Settings → AI Config 中切换。Paper Agent 的 Agent 模式待开发。

---

## 配置

**Alt+Shift+S** (Win/Linux) 或 **Cmd+Shift+S** (Mac) 打开 Settings：

- **Theme** — 主题
- **AI Config** — Agent 模式、Idea RAG、Self-Reflection、API Preset
- **Data** — Restore recent plan、Clear all data

---

## 项目结构

```text
maars/
├── backend/           # FastAPI + Socket.io
│   ├── api/           # 路由
│   ├── idea_agent/    # Idea Agent
│   ├── plan_agent/    # Plan Agent
│   ├── task_agent/    # Task Agent
│   ├── paper_agent/   # Paper Agent
│   ├── shared/        # llm_client、skill_utils、reflection 等
│   ├── visualization/ # 执行图布局
│   └── db/            # 文件存储
└── frontend/          # 静态页面、WebSocket
```

---

## 文档

| 文档 | 说明 |
| --- | --- |
| [docs/README.md](docs/README.md) | 文档索引 |
| [docs/DEVELOPMENT_GUIDE.md](docs/DEVELOPMENT_GUIDE.md) | 开发指南（架构、Skill 扩充与维护） |
| [docs/workflow/](docs/workflow/) | 工作流说明 |
| [docs/FRONTEND_SCRIPTS.md](docs/FRONTEND_SCRIPTS.md) | 前端脚本与模块依赖 |
| [docs/RELEASE_NOTE_STANDARD.md](docs/RELEASE_NOTE_STANDARD.md) | Release Note 撰写标准 |
