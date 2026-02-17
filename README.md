# MAARS

Multi-Agent Automated Research System（多智能体自动研究系统）

## 快速开始

### 1. 安装依赖

```bash
cd backend
python3 -m pip install -r requirements.txt
```

### 2. 启动服务

```bash
cd backend
python3 -m uvicorn main:asgi_app --host 0.0.0.0 --port 3001 --loop asyncio --http h11
```

或使用脚本：

```bash
cd backend
./run.sh
```

### 3. 访问应用

浏览器打开：**http://localhost:3001**

---

## 基本操作

| 操作 | 说明 |
|------|------|
| **输入 Idea** | 在输入框输入研究想法，点击 "Generate Plan" 生成任务计划 |
| **Load Example Idea** | 加载示例想法 |
| **Generate Plan** | 执行 AI 规划流程：Verify → Decompose → Format |
| **Stop** | 停止当前规划执行 |
| **Generate execution map** | 从 plan 提取 atomic tasks 生成 execution，渲染 Monitor 地图 |
| **Start Mock Execution** | 启动模拟执行 |

---

## 项目结构

```
maars/
├── backend/          # Python 后端
│   ├── main.py       # FastAPI + Socket.io 入口
│   ├── planner/      # 规划模块（verify/decompose/format）
│   ├── monitor/      # 监控模块
│   ├── executor/     # 执行器
│   ├── tasks/        # 任务缓存与阶段计算
│   ├── db/           # 数据存储
│   └── test/         # Mock 流式与测试工具
└── frontend/         # 前端页面
    ├── index.html
    ├── app.js
    └── styles.css
```

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PORT` | 3001 | 服务端口 |

---

## 测试说明

当前 Planner 使用 Mock AI 数据（`backend/db/test/mock-ai/`），无需配置真实 API 即可运行。
