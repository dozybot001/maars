# MAARS

Multi-Agent Automated Research System（多智能体自动研究系统）

## 快速开始

**前置**：已安装 [Python 3.10+](https://www.python.org/downloads/) 并勾选 “Add Python to PATH”。

```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn main:asgi_app --host 0.0.0.0 --port 3001 --loop asyncio --http h11
```

在浏览器中访问 **http://localhost:3001** 或 **http://127.0.0.1:3001**

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
- Monitor 依赖树布局（stage-based：stage 行 + 等价任务合并，详见 [STAGE_LAYOUT_RULES](backend/monitor/layout/STAGE_LAYOUT_RULES.md)）+ 网格布局

### Execution（执行）

Executor 池并行执行就绪任务，Validator 池验证输出，实时状态推送。LLM + Agent 模式下，Executor 使用多轮工具调用（ReadArtifact、ReadFile、WriteFile、Finish、ListSkills、LoadSkill），每个任务在独立沙箱中运行。

## 项目结构

```
maars/
├── backend/
│   ├── main.py          # FastAPI + Socket.io 入口
│   ├── api/             # 路由、schemas、state（按领域拆分）
│   ├── shared/          # 公共：graph 等
│   ├── planner/         # AI 规划（atomicity/decompose/format）
│   ├── monitor/         # execution 生成、依赖解析、网格布局
│   ├── executor/        # 执行：runner、execution
│   ├── validator/       # 验证：validator_manager
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

点击右上角 **API 配置** 进行设置：

- **AI Mode**：Mock（模拟数据）/ LLM（Planner+单次 Executor）/ LLM + Agent（Planner+多轮 Agent Executor）
- **Preset**：Base URL、API Key、Model（支持 OpenAI 兼容接口），支持按阶段独立配置
- **模式参数**：各 AI Mode 可调参数（如 Mock 通过率、Planner/Executor Temperature、Agent 最大轮数）

## 文档

- [前端脚本与模块依赖](docs/FRONTEND_SCRIPTS.md)
- [Release Note 标准](docs/RELEASE_NOTE_STANDARD.md) | [版本发布](docs/releases/) | 最新：[v3.1.0](docs/releases/RELEASE_v3.1.0.md)
- [后端结构](backend/README.md)（含各模块 README 链接）
- [执行图布局规则](backend/monitor/layout/STAGE_LAYOUT_RULES.md) | [Executor 改进规划](backend/executor/EXECUTOR_IMPROVEMENTS.md)
