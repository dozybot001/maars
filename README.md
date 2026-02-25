# MAARS

Multi-Agent Automated Research System（多智能体自动研究系统）

## 快速开始

```bash
cd backend
pip install -r requirements.txt
python3 -m uvicorn main:asgi_app --host 0.0.0.0 --port 3001 --loop asyncio --http h11
```

访问 **http://localhost:3001**

点击 **Load Example Idea** 可加载示例 idea：`Compare Python vs JavaScript for backend development and summarize pros/cons.`

## 工作流

### Generate Plan（规划阶段）

用户输入 idea → 后端递归分解任务树 → 保存 `plan.json`

- **Atomicity**：判断任务是否为原子任务
- **Decompose**：非原子任务分解为子任务（子任务仅含同级依赖）
- **Format**：为原子任务生成 input/output 规范

每次分解后，后端计算分解树布局（自实现 level-order 树布局，基于 task_id 层级），WebSocket 推送前端实时渲染。

### Generate Map（执行阶段）

从 plan 提取原子任务 → 解析依赖（继承+下沉） → 拓扑排序分 stage → 保存 `execution.json`

- 继承：原子任务继承祖先的跨子树依赖
- 下沉：非原子依赖目标替换为其原子后代
- Monitor 依赖树布局（stage-based：stage 行 + 等价任务合并，详见 [STAGE_LAYOUT_RULES](backend/layout/STAGE_LAYOUT_RULES.md)）+ 网格布局

### Execution（执行）

Executor 池并行执行就绪任务，Validator 池验证输出，实时状态推送。

## 项目结构

```
maars/
├── backend/
│   ├── main.py          # FastAPI + Socket.io 入口
│   ├── api/             # 路由、schemas、state（按领域拆分）
│   ├── planner/         # AI 规划（atomicity/decompose/format）
│   ├── monitor/         # execution 生成、依赖解析、网格布局
│   ├── layout/          # 分解树/执行图布局（tree_layout + stage_layout）
│   ├── workers/         # executor、validator、runner
│   ├── tasks/           # 任务阶段计算（拓扑排序、传递规约）
│   ├── db/              # 文件存储：db/{plan_id}/plan.json, execution.json
│   └── test/            # Mock AI 响应、mock_stream
└── frontend/
    ├── index.html
    ├── app.js           # 入口，模块组装
    ├── task-tree.js     # 任务树渲染（接收后端布局，纯渲染）
    ├── js/              # planner, planner-thinking, monitor, executor-thinking, websocket, api, config, theme
    ├── styles.css
    └── theme.css
```

## 配置 LLM API

默认使用 Mock AI（无需真实 API）。切换为 LLM 模式：

1. 点击右上角 **API 配置**
2. 填写 Base URL、API Key、Model（支持 OpenAI 兼容接口）
3. 关闭 Mock AI，保存

支持按阶段（atomicity check/decompose/format/quality assess/execute/validate）独立配置。

## 文档

- [前端脚本加载顺序与模块依赖](docs/FRONTEND_SCRIPTS.md)
- [Release Note 撰写标准](docs/RELEASE_NOTE_STANDARD.md) | [版本发布](docs/releases/)
- [后端结构](backend/README.md)
- [Layout 模块](backend/layout/README.md)（含 [执行图布局规则](backend/layout/STAGE_LAYOUT_RULES.md)）
- [Planner 流程](backend/planner/README.md)
- [Planner 改进建议](backend/planner/PLANNER_IMPROVEMENTS.md)（待开发特性）
- [执行阶段工作流](backend/workers/README.md)（Generate Map + Execution）
- [Executor 改进规划](backend/workers/EXECUTOR_IMPROVEMENTS.md)（Agent 化、Agent Skills、Atomicity 联动）
- [Monitor 模块](backend/monitor/README.md)
- [Test 模块](backend/test/README.md)
