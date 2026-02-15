# MAARS

Multi-Agent Automated Research System（多智能体自动研究系统）

## 快速开始

### 1. 安装依赖

```bash
cd backend
npm install
```

### 2. 启动服务

```bash
cd backend
npm start
```

或开发模式（自动重启）：

```bash
npm run dev
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
| **Load example execution** | 加载示例执行地图（Monitor 区域） |
| **Start Mock Execution** | 启动模拟执行 |

---

## 项目结构

```
maars/
├── backend/          # 后端服务
│   ├── server.js     # Express + Socket.io 主服务
│   ├── planner/      # 规划模块（verify/decompose/format）
│   ├── monitor/      # 监控模块
│   ├── executor/     # 执行器
│   └── db/           # 数据存储
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
