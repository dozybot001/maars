# MAARS

Multi-Agent Automated Research System — 多智能体自动研究系统。从模糊 idea 到论文草稿的一站式研究流水线。

中文｜[English](README.md)

## 快速开始

**前置**：Python 3.10+

```bash
git clone https://github.com/dozybot001/MAARS.git
cd MAARS/backend
pip install -r requirements.txt
python -m uvicorn main:asgi_app --host 0.0.0.0 --port 3001 --loop asyncio --http h11
```

或使用启动脚本：`./start.sh`（macOS/Linux）或 `start.bat`（Windows）。

访问 <http://localhost:3001> 进入界面。

## 工作原理

每个 **Research** 依次经过四个 Agent 驱动的阶段：

| 阶段 | Agent | 做什么 |
| --- | --- | --- |
| Refine | Idea | 提取关键词、arXiv 检索、生成 refined idea |
| Plan | Plan | 将 idea 分解为可执行任务树 |
| Execute | Task | 并行执行原子任务、验证产出 |
| Paper | Paper | 生成论文草稿（Markdown / LaTeX） |

每个阶段支持 **Run**、**Resume**、**Retry**、**Stop**。Agent 可在 Mock / LLM / Agent 模式间切换 — 在 Settings（**Cmd+Shift+S** / **Alt+Shift+S**）中配置。

## 文档

- [架构文档](docs/architecture_cn.md)（[English](docs/architecture.md)）
- [开发指南](docs/DEVELOPMENT_GUIDE.md)
- [全部文档](docs/README.md)
