# MAARS 第三方依赖介绍

本文档介绍项目使用的第三方库及其用途。

---

## 后端依赖 (Python)

### 核心框架

| 依赖 | 版本 | 介绍 |
|------|------|------|
| **fastapi** | ≥0.109.0 | 现代异步 Web 框架，自动生成 API 文档，内置 Pydantic 校验 |
| **uvicorn** | ≥0.27.0 | ASGI 服务器，用于运行 FastAPI 应用 |
| **python-socketio** | ≥5.10.0 | WebSocket 实时通信，用于 Planner 流式输出、Monitor 状态推送 |

### 工具库

| 依赖 | 版本 | 介绍 |
|------|------|------|
| **aiofiles** | ≥23.2.0 | 异步文件读写，用于 db 模块的 JSON 文件存储 |
| **networkx** | ≥3.0 | 图论库，用于任务依赖的拓扑排序与环检测 |
| **orjson** | ≥3.9.0 | 高性能 JSON 解析，比标准库 `json` 更快，用于 db、planner 的 JSON 读写 |

### LLM 相关

| 依赖 | 版本 | 介绍 |
|------|------|------|
| **openai** | ≥1.0.0 | OpenAI 官方 SDK，兼容 OpenAI 格式 API，用于调用 LLM（verify/decompose/format） |
| **tenacity** | ≥8.0.0 | 重试库，对 LLM 调用的连接错误、超时、限流进行指数退避重试 |
| **json-repair** | ≥0.7.0 | 修复畸形 JSON，用于解析 LLM 输出中的尾部逗号、未加引号 key 等常见错误 |

### 日志

| 依赖 | 版本 | 介绍 |
|------|------|------|
| **loguru** | ≥0.7.0 | 结构化日志库，替代标准 `logging`，输出更易读、支持上下文绑定 |

---

## 前端依赖 (CDN)

### 实时通信

| 依赖 | 版本 | 介绍 |
|------|------|------|
| **socket.io** | 4.5.4 | WebSocket 客户端，与后端保持长连接，接收 plan-thinking、task-states 等事件 |

### 内容渲染

| 依赖 | 版本 | 介绍 |
|------|------|------|
| **marked** | - | Markdown 解析，将 AI Thinking 的 Markdown 转为 HTML |
| **DOMPurify** | 3.0.9 | HTML 净化，对 marked 输出做 XSS 过滤，防止用户/AI 内容注入脚本 |
| **highlight.js** | 11.9.0 | 代码高亮，为 AI Thinking 中的代码块添加语法高亮 |

### 可视化

| 依赖 | 版本 | 介绍 |
|------|------|------|
| **dagre** | 0.8.5 | DAG 图布局算法，用于 Planner/Monitor 任务树的节点排布，减少边交叉 |

### 工具

| 依赖 | 版本 | 介绍 |
|------|------|------|
| **lodash** | 4.17.21 | 工具函数库，使用 `_.debounce` 对窗口 resize 做防抖 |

---

## 依赖关系简图

```
后端:
  FastAPI + uvicorn (Web 服务)
       ├── python-socketio (WebSocket)
       ├── aiofiles (异步文件)
       ├── orjson (JSON 读写)
       ├── networkx (任务图)
       ├── openai + tenacity (LLM 调用)
       ├── json-repair (解析 AI JSON)
       └── loguru (日志)

前端:
  socket.io (实时通信)
  marked → DOMPurify (Markdown → 安全 HTML)
  highlight.js (代码高亮)
  dagre (任务树布局)
  lodash (防抖等)
```

---

## 参考链接

- [FastAPI](https://fastapi.tiangolo.com/)
- [OpenAI Python SDK](https://github.com/openai/openai-python)
- [json-repair](https://github.com/mangiucugna/json_repair)
- [loguru](https://github.com/Delgan/loguru)
- [dagre](https://github.com/dagrejs/dagre)
- [DOMPurify](https://github.com/cure53/DOMPurify)
- [highlight.js](https://highlightjs.org/)
- [lodash](https://lodash.com/)
