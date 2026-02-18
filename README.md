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
| 输入 Idea + Generate Plan | AI 规划：Verify → Decompose → Format |
| Load Example Idea | 加载示例想法 |
| Generate execution map | 从 plan 生成 execution，渲染 Monitor 地图 |
| Mock Execution | 模拟执行 |
| 主题切换 | 右上角 ☀/🌙/◻ 切换 Light / Dark / Black |

## 项目结构

```
maars/
├── backend/
│   ├── main.py          # FastAPI + Socket.io
│   ├── planner/         # 规划（verify/decompose/format）
│   ├── monitor/         # 布局、execution 生成
│   ├── workers/         # executor、verifier、runner
│   ├── tasks/           # 任务缓存与阶段
│   ├── db/              # db/{plan_id}/plan.json, execution.json, verification.json
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
