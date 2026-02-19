# MAARS

Multi-Agent Automated Research System（多智能体自动研究系统）

## 快速开始

```bash
cd backend
pip install -r requirements.txt
python3 -m uvicorn main:asgi_app --host 0.0.0.0 --port 3001 --loop asyncio --http h11
```

访问 **http://localhost:3001**

## 基本操作

| 操作 | 说明 |
|------|------|
| 输入 Idea + Generate Plan | AI 规划：Atomicity → Decompose → Format |
| Load Example Idea | 加载示例想法 |
| Generate Map | 从 plan 生成 execution，渲染 Monitor 地图 |
| Execution | 执行任务（Mock AI 模式为模拟执行，LLM 模式为真实调用） |
| 主题切换 | 右上角 ☀/🌙/◻ 切换 Light / Dark / Black |

## 项目结构

```
maars/
├── backend/
│   ├── main.py          # FastAPI + Socket.io
│   ├── planner/         # 规划（atomicity/decompose/format）
│   ├── monitor/         # 布局、execution 生成
│   ├── workers/         # executor、validator、runner
│   ├── tasks/           # 任务缓存与阶段
│   ├── db/              # db/{plan_id}/plan.json, execution.json, validation.json
│   └── test/            # Mock AI、mock_stream
└── frontend/
    ├── index.html
    ├── app.js
    ├── task-tree.js
    ├── styles.css
    └── theme.css
```

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| PORT | 3001 | 服务端口 |

## 说明

Planner 使用 Mock AI（`backend/test/mock-ai/`），无需配置真实 API 即可运行。

## 文档

- [后端结构](backend/README.md)
- [Planner 流程](backend/planner/README.md)
- [任务树与 Timetable](backend/docs/task-tree-timetable.md)
- [第三方依赖](backend/docs/DEPENDENCIES.md)
