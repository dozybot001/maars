## MAARS

目前暂时为**可视化任务分解与拓扑排序执行的前端监控界面**。支持输入研究任务、生成结构化计划（任务分解）、按依赖关系进行拓扑排序并生成执行图，同时监控执行器与验证器的运行状态。

> **当前状态**：目前仅实现上述功能，后续会继续完善与扩展。

## 功能概览

- **任务分解（Planner）**：输入研究任务，通过配置的 AI API 生成结构化计划（子任务及依赖关系）。
- **执行图与拓扑排序（Dispatcher）**：根据计划中的依赖关系进行拓扑排序，生成分阶段执行序列，并在前端以**时间表式布局**展示任务依赖图（节点、连线、阶段列）。
- **执行监控**：实时展示 **Executors**（执行器）与 **Verifiers**（验证器）的数量与状态（Total / Busy / Idle），支持 Mock 执行演示。

## 主要特性

- **输入区**：填写研究任务描述。
- **输出区**：展示生成的计划文本。
- **执行图**：可视化展示任务依赖与拓扑排序结果（列表示阶段，节点间连线表示依赖）。
- **设置**：配置 API（URL、API Key、Model、Temperature）。
- **示例与 Mock**：支持加载示例计划、生成执行图、Mock 执行以便联调与演示。

## 快速开始

### 后端

```bash
cd backend
npm install
npm start
```

默认运行在 `http://localhost:3001`。若端口被占用可指定：`PORT=3002 npm start`（需同步修改前端的 `API_BASE_URL` / `WS_URL`）。

### 前端

后端会托管前端静态资源。在浏览器中打开：

```
http://localhost:3001
```

也可直接打开 `frontend/index.html`（直接打开时可能受 CORS 限制，建议通过后端访问）。

## 使用流程

1. **设置**：点击 “Settings” 配置 API URL、API Key、模型与 Temperature。
2. **生成计划**：在输入区填写研究任务，点击 “Generate Plan” 得到任务分解结果。
3. **生成执行图**：计划生成后，点击 “Generate Execution Map” 根据依赖关系进行拓扑排序并渲染执行图。
4. **监控执行**：在 Dispatcher 中可 “Load Example” / “Mock Execution”，在 Executors / Verifiers 区域查看状态变化。

## 项目结构

```
mvp/
├── backend/
│   ├── server.js           # Express + Socket.IO 服务与 API
│   ├── planner/            # 计划生成（任务分解）
│   ├── dispatcher/         # 执行阶段与拓扑排序、时间表布局（timetable.js）
│   ├── executor/           # 执行器管理
│   ├── verifier/           # 验证器管理
│   ├── db/                 # 计划存储
│   └── package.json
├── frontend/
│   ├── index.html          # 主页面（Planner / Dispatcher / Executors / Verifiers）
│   ├── styles.css          # 样式
│   └── app.js              # 前端逻辑、执行图渲染、WebSocket 监控
└── README.md
```

## API 概览

- `GET /api/config` — 获取当前 API 配置  
- `POST /api/config` — 更新 API 配置  
- `POST /api/plan` — 根据任务描述生成计划（任务分解）  
- 其他接口用于执行图、执行器/验证器状态等，详见 `backend/server.js`

---

**总结**：**前端监控与可视化**，实现从任务输入 → 任务分解 → 拓扑排序 → 执行图展示 → 执行/验证状态监控的完整界面。当前为阶段性实现，功能将陆续完善。
