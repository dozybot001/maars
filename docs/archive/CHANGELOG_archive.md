# MAARS Release Notes Archive

> 归档时间：2026-04-18

## MAARS v1.0.0 `v1.0.0`

*发布于 2026-02-17*

- 后端改为 Python 实现
- 打通 Monitor 和 Planner：execution.json 会提取 plan.json 的原子任务绘制执行地图
- 新增主题切换：Light / Dark / Black
- 统一、优化 UI 设计：Planner 采用左右布局，AI Thinking 支持并发流式
- 修复部分 BUG
- 部分功能采用更稳健的方式实现

---

## MAARS v2.0.0 `v2.0.0`

*发布于 2026-02-18*

- 接入真实 LLM API，用户可自行配置
- DB 引入 Plan ID 命名文件夹，后端引入 Plan ID 作为 Plan 标识
- 采用 Dagre 重构任务树布局，提升可视化效果
- 引入其他第三方库以提升项目稳健性并简化代码，详情参考 [docs/DEPENDENCIES.md](https://github.com/dozybot001/maars/blob/main/backend/docs/DEPENDENCIES.md)

---

## MAARS v2.1.0 `v2.1.0`

*发布于 2026-02-19*

- 部分阶段命名调整：Verify (for atomic tasks) -> Atomicity，Verify (for tasks' output verification) -> Validate
- 完善 Planner 工作流，Format 分为两个阶段：IO & Validation Definition
- DB 结构新增：Plan ID 文件夹下的 Task ID 文件夹，用于储存上下游依赖产物 (Artifacts)
- 支持多阶段独立配置 API ：Atomicity、Decompose、Format、Execute、Validate
- 新增分解质量评价
- Execution 的纯 LLM 实现，“LLM + Tools Pool” Agent 模式待开发

---

## MAARS v2.2.0 `v2.2.0`

*发布于 2026-02-23*

## 2026-02-23

### 新增

- **模块化 API**（`backend/api/`）：按领域拆分路由（db、plan、plans、execution、monitor、config、workers、validation）
- **Layout 模块**（`backend/layout/`）：Sugiyama 分层 DAG 布局与任务分解树布局
- **Planner 思考流**：前端 `planner-thinking.js` 支持规划阶段思考过程实时展示

### 变更

- **Format 阶段合并**：将 `format_io` 与 `format_validate` 合并为单一 `format` 阶段，简化原子任务 I/O 规范生成
- **Atomicity 上下文增强**：atomicity 阶段支持 depth、ancestor_path、idea、siblings 等上下文
- **main.py 精简**：路由迁移至 api 模块，main.py 仅保留入口与注册
- **前端主题与样式**：更新 theme.js、theme.css、styles.css，优化任务树与 UI
- **任务树渲染**：task-tree.js 重构，接收后端布局数据、专注渲染

### 移除

- `backend/planner/graph_utils.py`（逻辑迁移至 layout 模块）
- `format-io-prompt.txt`、`format-validate-prompt.txt`（合并为 `format-prompt.txt`）
- `backend/docs/DEPENDENCIES.md`、`task-tree-timetable.md`
- Mock AI：`format_io.json`、`format_validate.json`

### 文档

- 更新 README.md、backend/README.md、planner/README.md、test/README.md

---

## MAARS v2.3.0 `v2.3.0`

*发布于 2026-02-24*

### 新增 (Added)

- **Stage 布局算法**：Monitor 执行图采用全新的 stage-based 布局，替代原 Sugiyama 分层 DAG 算法
  - 按 `stage` 分层排列任务，每 stage 一行
  - 等价任务合并：相同上下游的原子任务合并为单一节点显示
  - 跨层连线：相邻层实线、跨层虚线区分
  - 排序与对齐规则详见 `backend/layout/STAGE_LAYOUT_RULES.md`

- **合并节点支持**：执行图中合并节点支持多任务详情
  - 任务详情弹窗支持 Tab 切换查看合并节点内各任务
  - 合并单元格状态聚合（doing/done/failed 等）
  - 高亮连线支持一对多、多对一边缘

- **JetBrains Mono 字体**：全局采用 JetBrains Mono 等宽字体，提升代码与任务 ID 可读性

- **Timetable 单元格主题变量**：新增 `--timetable-cell-bg`、`--timetable-cell-empty-bg`、`--timetable-cell-hover-bg`，支持亮/暗主题下任务格与空格的区分

### 变更 (Changed)

- **Layout 模块重构**：
  - 移除 `sugiyama.py`（458 行），依赖 graph 构建逻辑移至 `graph.py`
  - 新增 `graph.py`：`build_dependency_graph`、`natural_task_id_key` 统一供 planner、tasks、layout 使用
  - 新增 `stage_layout.py`：实现 stage 行布局与等价任务合并
  - `compute_tree_layout` 重命名为 `compute_monitor_layout`，语义更清晰

- **前端任务树**：
  - 支持 `nodes` 中 `pos.ids` 表示合并节点
  - 连线支持 `from`/`to` 为数组（多对一/一对多）
  - 跨层连线使用 `connection-line-cross-layer` 样式

- **WebSocket 状态更新**：支持 `data-task-ids` 单元格，合并单元格内任一任务状态变化时正确更新显示

- **任务详情弹窗**：点击外部关闭时排除 `timetable-cell`，避免误关

- **样式微调**：`--border-radius` 8px、`--tree-task-radius` 10px

### 修复 (Fixed)

- **Execution Stop**：`/stop` 路由正确引用 `api_state.executor_runner` 停止执行

### 移除 (Removed)

- `backend/layout/sugiyama.py`：Sugiyama 分层图布局算法（由 stage_layout 替代）

### 依赖 (Dependencies)

- 移除对 `networkx` 在 layout 中的直接使用（graph 构建仍使用 networkx，由 `tasks` 和 `planner` 调用）

---

## MAARS v2.3.1 `v2.3.1`

*发布于 2026-02-24*

### 前端

#### 样式重构
- **模块化 CSS**：将 `styles.css` 拆分为多个模块，便于维护与扩展
  - `css/theme.css` - 主题色板
  - `css/base.css` - 变量、reset、滚动条
  - `css/layout.css` - 页头、区块、排版
  - `css/planner.css` - Planner 区块
  - `css/monitor.css` - Monitor 区块
  - `css/components.css` - 通用组件
  - `css/api-config.css` - API 配置弹窗
  - `css/task-tree.css` - 任务树与执行图
  - `css/executor.css` / `css/validator.css` - 执行器与验证器
- **主题文件迁移**：`theme.css` 移至 `css/` 目录
- **样式文档**：新增 `frontend/css/README.md` 说明样式结构与加载顺序

#### UI 调整
- 缩小 Monitor 下方执行图区域高度，优化布局

### 文档
- 新增 `backend/monitor/README.md` - Monitor 模块说明
- 新增 `backend/planner/PLANNER_IMPROVEMENTS.md` - Planner 改进建议
- 新增 `backend/workers/README.md` - 执行阶段工作流说明
- 更新 `README.md` 与 `backend/README.md`

---

## MAARS v2.4.0 `v2.4.0`

*发布于 2026-02-24*

**发布日期**：2026-02-25

## 概述

本版本聚焦 Executor 模块体验升级：支持 LLM 执行时的**流式思考输出**，用户可在执行阶段实时查看 AI 生成过程；同时重构 Executor 区域 UI，新增 AI Thinking 与 Task Output 双栏展示，并补充 Executor 改进规划文档。

## 新增功能 (Added)

- **Executor**：LLM 执行支持流式输出（streaming），通过 `on_thinking` 回调实时推送生成内容至前端
- **Executor**：新增 AI Thinking 区域，展示执行过程中的实时思考内容（支持 Markdown 渲染、代码高亮、节流渲染）
- **Executor**：新增 Task Output 区域，展示每个任务完成后的最终输出
- **WebSocket**：新增 `execution-start`、`executor-thinking`、`executor-output` 事件，用于执行阶段状态与内容推送
- **Mock 模式**：Mock AI 模式下同样支持模拟流式输出，便于本地调试
- **文档**：新增 [Executor 改进规划](backend/workers/EXECUTOR_IMPROVEMENTS.md)，记录 Agent 化与 Agent Skills 接入方向

## 变更 (Changed)

- **Executor UI**：重构 Executor 区域布局，stats 与 chips 分离，AI Thinking 与 Task Output 采用双栏并排展示
- **Executor UI**：新增 Idle 统计展示，优化 executor chips 与 thinking/output 区域样式
- **Runner**：执行开始时 emit `execution-start`，任务完成时 emit `executor-output`，便于前端同步状态
- **Layout**：`stage_layout` 优化空 `slot_positions` 处理逻辑；`tree_layout` 补充居中策略注释
- **API**：`plan.py` 抽取 `_tree_update_payload` 复用 treeData + layout 构建逻辑

## 修复 (Fixed)

- （本版本无专项 Bug 修复）

## 技术细节

- **流式执行**：`llm_executor.execute_task` 新增 `on_thinking` 参数，当传入时启用 `stream=True`，逐 chunk 回调
- **前端模块**：`executor-thinking.js` 负责接收 WebSocket 数据、节流渲染、滚动保持与用户滚动状态检测

---

## MAARS v2.4.1 `v2.4.1`

*发布于 2026-02-24*

**发布日期**：2026-02-25

## 概述

本版本建立 Release Note 撰写规范与发布流程，新增撰写标准文档、 releases 归档目录及 v2.4.0 历史 Release Note，并在 README 中增加文档入口。

## 新增功能 (Added)

- **文档**：新增 [Release Note 撰写标准](docs/RELEASE_NOTE_STANDARD.md)，定义版本号规则、结构模板、分类说明与撰写原则
- **文档**：新增 `docs/releases/` 目录，用于归档各版本 Release Note
- **文档**：补充最近 Release Note 历史记录

## 变更 (Changed)

- **README**：文档章节新增 Release Note 撰写标准链接

## 修复 (Fixed)

- （本版本无专项 Bug 修复）

---

## MAARS v2.5.0 `v2.5.0`

*发布于 2026-02-25*

**发布日期**：2026-02-25

## 概述

本版本为 Validator 模块新增 AI Thinking 流式输出，验证阶段可实时查看 AI 思考过程；同时重构前端 Thinking 区域实现，抽取统一的 `thinking-area` 工厂供 Planner、Executor、Validator 共用，并建立按钮设计规范与前端脚本加载文档。

## 新增功能 (Added)

- **Validator**：支持 AI Thinking 流式输出，验证阶段实时展示 AI 思考内容（Mock 模式下模拟验证报告逐步显示）
- **前端**：新增 `thinking-area.js` 工厂，统一 Planner/Executor/Validator 的 Thinking 区域实现（节流渲染、滚动保持、Markdown/代码高亮）
- **前端**：新增 `validator-thinking.js` 模块，对接 WebSocket `validator-thinking` 事件
- **前端**：新增 `constants.js`，集中管理魔法数字（RENDER_THROTTLE_MS、LARGE_CONTENT_CHARS 等）
- **前端**：新增 `utils.js`，提供 escapeHtml、escapeHtmlAttr 等工具函数
- **WebSocket**：新增 `validator-thinking` 事件，用于验证阶段流式内容推送
- **文档**：新增 [前端脚本加载顺序与模块依赖](docs/FRONTEND_SCRIPTS.md)
- **文档**：新增 [按钮设计规范](frontend/css/BUTTON_DESIGN.md)

## 变更 (Changed)

- **Planner-thinking**：精简实现，改用 `createThinkingArea` 工厂
- **Executor-thinking**：重构实现，改用 `createThinkingArea` 工厂
- **CSS**：`icon-btn`、`theme-toggle-btn` 等从 layout.css 迁移至 components.css，统一按钮规范
- **CSS**：api-config.css 精简，validator.css 扩展 validator-thinking 样式
- **Runner**：Mock 模式下 emit `validator-thinking` 流式内容，与 Executor 体验一致
- **index.html**：新增 Validator AI Thinking 区域及 validator-thinking.js 引用

## 技术细节

- **thinking-area 工厂**：`createThinkingArea(config)` 接收 prefix、contentElId、areaElId、blockClass，返回 clear、appendChunk、render、applyHighlight，内部统一节流与滚动逻辑
- **脚本加载顺序**：utils → task-tree → config → constants → theme → api → planner → thinking-area → planner-thinking / executor-thinking / validator-thinking → monitor → websocket → app

## 修复 (Fixed)

- （本版本无专项 Bug 修复）

---

## MAARS v3.0.0 `v3.0.0`

*发布于 2026-02-26*

**发布日期**：2026-02-26

## 概述

本版本为 **major** 升级：Executor 从单次 LLM 调用升级为支持多轮决策与工具调用的 **Agent 形态**，每个任务在独立沙箱中运行；同时完善 API 配置页，支持 Mock / LLM / LLM+Agent 三种模式的参数化配置。

## 新增功能 (Added)

- **Executor Agent**：新增 LLM + Agent 模式，Executor 使用多轮 ReAct 循环与工具调用（Planner 仍为 LLM 分解）
- **Agent 工具**：ReadArtifact（读取依赖任务输出）、ReadFile（读取 plan 目录及沙箱文件）、WriteFile（写入沙箱）、Finish（提交最终输出）、ListSkills、LoadSkill（Agent Skills 指令注入）
- **沙箱隔离**：每个 task 对应独立沙箱目录 `db/{plan_id}/{task_id}/sandbox/`，工具执行限定于此，支持路径穿越防护
- **API 配置**：AI Mode 配置页支持 Mock / LLM / LLM+Agent 三种模式，各模式提供可调参数
- **Mock 参数**：执行通过率、验证通过率、最大重试次数（原环境变量现可在 UI 配置）
- **LLM 参数**：Planner Temperature、Executor LLM Temperature
- **LLM+Agent 参数**：Planner Temperature、Executor LLM Temperature、Executor Agent 最大轮数
- **LLM 客户端**：`chat_completion` 支持 `tools` 参数及 `tool_calls` 响应，用于 Agent 模式

## 变更 (Changed)

- **配置结构**：`api_config.json` 新增 `modeConfig`，按模式存储可调参数
- **配置解析**：`_resolve_api_config` 合并 `modeConfig`，Runner/Executor 从配置读取参数
- **Executor**：`executorAgentMode=true` 时启用 Agent 循环，`max_turns` 可配置
- **API 配置 UI**：Mock/LLM/LLM+Agent 各模式配置页按模块分组（LLM (Planner)、Executor LLM、Executor Agent）
- **agent_tools**：复用 `db._validate_plan_id`，移除重复实现

## 修复 (Fixed)

- （本版本无专项 Bug 修复）

## 技术细节 / 迁移指南

- **启用 Agent 模式**：API 配置 → AI Mode 选择「LLM + Agent」→ 保存
- **沙箱路径**：`db/{plan_id}/{task_id}/sandbox/`，ReadFile 使用 `sandbox/X` 读取沙箱内文件
- **Skills 目录**：环境变量 `MAARS_SKILLS_DIR` 或默认 `backend/skills/`
- **向后兼容**：旧配置中的 `temperature`、`maxTurns` 自动映射为 `executorLlmTemperature`、`executorAgentMaxTurns`

---

## MAARS v3.1.0 `v3.1.0`

*发布于 2026-02-26*

**发布日期**：2026-02-26

## 概述

本版本对后端进行按区域重构，将 `layout`、`tasks`、`workers` 拆分为 `planner`、`monitor`、`executor`、`validator` 四大区域，并补充各目录 README 文档。

## 新增功能 (Added)

- **shared/**：新增公共模块，`graph.py` 提供 `build_dependency_graph`、`natural_task_id_key`，供 planner、monitor 共用
- **文档**：各模块目录新增 README（api、db、shared、planner/layout、planner/prompts、monitor/layout、monitor/tasks、executor/execution、test/mock-ai 等）

## 变更 (Changed)

- **后端结构**：按 planner、monitor、executor、validator 区域解耦
- **planner**：新增 `layout/tree_layout.py`，分解树布局从根 layout 迁入
- **monitor**：新增 `layout/stage_layout.py`、`tasks/task_stages.py`、`tasks/task_cache.py`，执行图布局与任务阶段计算迁入
- **executor**：从 workers 拆分，含 runner、execution、executor_manager
- **validator**：从 workers 拆分，含 validator_manager
- **文档**：backend/README 精简为目录表，各模块 README 统一风格、避免冗余
- **.gitignore**：新增 `*.qkdownloading` 忽略下载临时文件

## 移除 (Removed)

- **layout/**：已拆分至 planner/layout、monitor/layout、shared
- **tasks/**：已迁入 monitor/tasks
- **workers/**：已拆分至 executor、validator

## 技术细节 / 迁移指南

- **导入路径**：若外部代码直接引用 `layout`、`tasks`、`workers`，需改为 `planner.layout`、`monitor.layout`、`monitor.tasks`、`executor`、`validator`、`shared.graph`
- **API 行为**：无变更，路由与响应格式保持兼容
- **配置**：无变更

---

## MAARS v4.0.0 `v4.0.0`

*发布于 2026-02-27*

**发布日期**：2026-02-28

## 概述

本版本将 Monitor 模块并入 Planner，形成 planner/visualization 统一负责分解树与执行图；Skills 按 Planner/Executor 拆分至各自目录；API 路由由 workers/monitor 调整为 executors/validation。架构简化，导入路径有破坏性变更。

## 新增功能 (Added)

- **planner/visualization/**：执行图与 layout 统一由 Planner 负责，含 `build_execution_from_plan`、`build_layout_from_execution`、stage 布局、timetable
- **planner/skills/**：Planner Agent 技能（atomicity-criteria、decomposition-patterns、format-specs、dependency-rules、research-scoping）
- **executor/skills/**：Executor Agent 技能（find-skills、skill-creator、markdown-reporter、data-analysis、comparison-report、literature-synthesis、json-utils、web-research）
- **planner/agent_tools**：Planner Agent 工具调用
- **executor/pools.py**：Executor 池管理
- **executor/validation.py**：独立 validation 模块
- **API**：`/api/executors`、`/api/validation` 路由

## 变更 (Changed)

- **Monitor 并入 Planner**：`execution.json` 由 `planner.visualization.build_execution_from_plan` 生成，layout 由 `planner.visualization.build_layout_from_execution` 生成
- **API 路由**：workers → executors，monitor 端点移除，layout 并入 plan
- **Planner**：支持 Agent 模式，多轮工具调用
- **文档**：README、backend README 更新为当前结构，STAGE_LAYOUT_RULES 路径更新至 `planner/visualization/layout/`
- **发版流程**：不再维护 `docs/releases/`，Release Note 以代码块输出

## 移除 (Removed)

- **backend/monitor/**：整个模块删除，逻辑迁入 planner/visualization
- **backend/skills/**：原根目录 skills（algorithmic-art、canvas-design、docx 等）删除，技能现位于 planner/skills、executor/skills
- **api/routes/workers.py**、**api/routes/monitor.py**
- **EXECUTOR_IMPROVEMENTS.md**、**PLANNER_IMPROVEMENTS.md**
- **docs/releases/**：Release 文件目录
- **前端**：monitor.js、validator-thinking.js、monitor.css、validator.css（逻辑并入 planner-views、thinking-area）

## 技术细节 / 迁移指南

- **导入路径**：`monitor.*`、`from_plan`、`monitor.layout` 等改为 `planner.visualization`、`planner.visualization.from_plan`、`planner.visualization.layout`
- **API**：`/api/workers/*` 已移除，使用 `/api/executors`；`/api/monitor/*` 已移除，layout 通过 `/api/plan/layout` 获取
- **Skills**：原 `backend/skills/` 下技能已迁移或移除，使用 `planner/skills/`、`executor/skills/` 中技能

---

## MAARS v4.0.1 `v4.0.1`

*发布于 2026-02-27*

**发布日期**：2026-02-28

## 概述

精简 README 与文档结构，删除 16 个冗余子模块 README，补充 Planner/Executor Agent 工作流说明。

## 变更 (Changed)

- **README**：重写核心流程，新增 Planner Agent、Executor Agent 工具表
- **backend/README**：精简结构表，移除子模块链接
- **文档**：保留 STAGE_LAYOUT_RULES 链接

## 移除 (Removed)

- **16 个子模块 README**：api、api/routes、planner、planner/layout、planner/prompts、planner/visualization、planner/visualization/layout、planner/visualization/tasks、shared、db、executor/execution、test、test/mock-ai、frontend/css、planner/skills、executor/skills

---

## MAARS v4.1.0 `v4.1.0`

*发布于 2026-02-28*

**发布日期**：2025-02-28

## 概述

本版本将 API 配置重构为统一 Settings，并调整模块命名与 UI。后端统一使用 `settings.json`，前端通过 Alt+Shift+S 打开设置弹窗。

## 新增功能 (Added)

- **Settings 弹窗**：Theme（主题选择）、DB Operation（Restore/Clear）、AI Mode、Preset 集中管理
- **快捷键**：Alt+Shift+S 打开 Settings
- **后端**：`/api/settings` 替代 `/api/config`，`settings.json` 替代 `api_config.json`

## 变更 (Changed)

- **后端**：`planner/` → `plan/`，`executor/` → `execution/`，`api_config` → `settings`
- **前端**：移除主页面图标按钮，CSS 文件 `planner.css` → `plan.css`，`executor.css` → `execution.css`
- **配置**：`get_settings()`、`save_settings()`、`get_effective_config()` 替代原 API 配置接口
- **迁移**：若存在 `api_config.json` 且无 `settings.json`，首次启动会自动迁移

## 修复 (Fixed)

- 合并重复的 `_get_parent_id`、`_get_ancestor_path` 等辅助函数到 `plan.graph`
- 合并重复的 Markdown 样式到 `components.css`
- 移除未使用的主题变量与表单样式

## 技术细节 / 迁移指南

- 首次升级：若本地有 `api_config.json`，会自动迁移到 `settings.json`
- 前端：`fetchSettings()`、`saveSettings()` 请求 `/api/settings`
- `.gitignore` 已更新为忽略 `settings.json` 与 `api_config.json`

---

## MAARS v4.2.0 `v4.2.0`

*发布于 2026-02-28*

**发布日期**：2025-02-28

## 概述

后端模块解耦与共享化：visualization 独立、shared 模块统一、plan 与 execution 解耦；Settings 统一为 settings.json；Agent 模式下 Plan 支持降级为 LLM。

## 新增功能 (Added)

- **Agent 模式**：Plan 支持降级为 LLM，可在 Settings → AI Mode → Agent 中通过「Plan Agent」开关切换
- **shared 模块**：新增 `backend/shared/`，统一 graph、llm_client、skill_utils、utils 等共享逻辑

## 变更 (Changed)

- **后端架构**：visualization 从 plan 移至 backend 根目录，plan 专注业务逻辑，visualization 专注布局计算
- **plan 与 execution 解耦**：llm_client 移至 shared，execution 不再依赖 plan
- **Settings**：配置统一存于 `settings.json`，移除 api_config.json 兼容逻辑
- **Theme**：主题由 localStorage 改为存入 settings.json
- **前端**：api-config 重命名为 settings，导航精简为 Theme、DB Operation、AI Mode、Preset

## 弃用/移除 (Deprecated / Removed)

- 移除 `api_config.json` 及迁移逻辑
- 移除 `backend/plan/graph.py`、`backend/plan/llm_client.py`（已迁移至 shared）
- 移除 `backend/plan/visualization/`（已迁移至 `backend/visualization/`）
- 移除 `frontend/css/api-config.css`（已重命名为 settings.css）

## 技术细节 / 迁移指南

- 若本地存在 `api_config.json`，需在 Settings 中重新配置 Preset 并保存
- API 行为保持兼容，仅内部模块与配置存储方式调整

---

## MAARS v4.3.0 `v4.3.0`

*发布于 2026-02-28*

**发布日期**：2025-02-28

## 概述

本版本对后端与前端进行模块重构：将 `plan/`、`execution/` 重命名为 `plan_agent/`、`task_agent/`，统一命名；前端合并 thinking 相关模块，简化脚本依赖；同步更新文档。

## 新增功能 (Added)

- 无

## 变更 (Changed)

- **Backend**：`plan/` → `plan_agent/`，`execution/` → `task_agent/`，技能目录随模块迁移
- **Backend**：移除 `/api/validation`、`/api/workers` 路由
- **Frontend**：`planner.js` → `plan.js`，`planner-views.js` → `views.js`，`task-tree.js` 移至 `js/`
- **Frontend**：合并 `planner-thinking`、`executor-thinking`、`thinking-area` 为 `thinking.js`
- **Frontend**：移除 `constants.js`，魔法数字内联
- **Docs**：`docs/FRONTEND_SCRIPTS.md` 更新为当前脚本加载顺序与依赖

## 修复 (Fixed)

- 无

## 弃用/移除 (Deprecated / Removed)

- `/api/validation`、`/api/workers` 路由已移除

---

## MAARS v4.4.0 `v4.4.0`

*发布于 2026-02-28*

**发布日期**：2026-02-28

## 概述

将 Task Agent 的验证逻辑拆分为 LLM 模式与 Agent 模式：LLM 模式沿用系统级 LLM 校验，Agent 模式改为由 Agent 在 Finish 前通过 task-output-validator 技能自检。

## 新增功能 (Added)

- **Task Agent**：新增 task-output-validator 技能，支持在 Finish 前对输出做结构化校验（JSON schema、Markdown 章节等）

## 变更 (Changed)

- **Task Agent**：验证逻辑移至 `task_agent/llm/validation.py`，仅在 LLM 模式下由系统调用
- **Task Agent**：Agent 模式下由 Agent 在 Finish 前通过 task-output-validator 技能自检，系统不再做二次校验
- **Task Agent**：Agent prompt 增加 validation 规则，有 validation spec 时要求先校验再 Finish
- **Plan Agent**：prompt 重命名与调整（plan-agent-prompt）

## 修复 (Fixed)

- （无）

---

## MAARS v4.5.0 `v4.5.0`

*发布于 2026-02-28*

**发布日期**：2025-02-28

## 概述

本版本增强 Task Agent 的调研与引用能力：新增 WebSearch/WebFetch 工具支持实时网页搜索与 URL 抓取；强化调研报告的引用与来源规范，要求包含 References 小节；Format 阶段自动为研究任务加入引用校验。

## 新增功能 (Added)

- **Task Agent**：新增 WebSearch 工具，支持 DuckDuckGo 网页搜索，用于调研、基准测试、官方文档等
- **Task Agent**：新增 WebFetch 工具，支持抓取 URL 内容，用于报告中的真实引用
- **source-attribution 技能**：新增引用规范技能，用于引用密集型任务
- **format-specs / format-prompt**：研究/对比类报告自动加入「Document has ## References section」「References section is non-empty」校验

## 变更 (Changed)

- **markdown-reporter**：增加 References 与引用格式说明，要求调研报告包含 ## References 小节
- **web-research**：更新为支持 WebSearch/WebFetch，强化引用与来源要求
- **literature-synthesis / comparison-report**：将 References 小节设为必填，定量数据需标注来源
- **task-output-validator**：支持「References section is non-empty」校验
- **依赖**：新增 duckduckgo-search、httpx（Web 工具依赖）

## 技术细节

- Web 工具可通过 `MAARS_TASK_WEB_ENABLED=0` 禁用
- 安装依赖：`pip install -r requirements.txt`

---

## MAARS v4.5.1 `v4.5.1`

*发布于 2026-02-28*

**发布日期**：2025-02-28

## 概述

本版本移除主界面上的「Concurrent: 0 / 7」并发统计显示，简化 UI。

## 变更 (Changed)

- **前端**：移除任务执行区域的 Concurrent 统计展示

---

## MAARS v4.6.0 `v4.6.0`

*发布于 2026-02-28*

**发布日期**：2025-02-28

## 概述

本版本主要增强 Thinking 区域的调度信息展示，并修复 Output 区域对 Agent Finish 输出的渲染问题。Plan/Execute 阶段会显示更详细的进度与工具调用参数摘要，任务输出中的 Markdown 内容可正确渲染。

## 新增功能 (Added)

- **Thinking 区域**：调度信息展示增强，包含阶段（Plan/Execute）、轮次（Turn X/Y）、任务 ID（Task X）、工具名及参数摘要（如 `ReadFile(path: sandbox/notes.txt)`、`Decompose(task_id: 0)`）。连续的调度信息增加高度限制。
- **backend/shared/utils**：新增 `format_tool_args_preview()`，用于从工具参数 JSON 生成可读摘要

## 变更 (Changed)

- **Plan Agent / Task Agent**：`schedule_info` 增加 `operation`、`tool_args_preview`、`task_id`（Task Agent）字段
- **README**：补充 Thinking 区域展示说明

## 修复 (Fixed)

- **Output 区域**：修复 Agent Finish 工具输出 `{ content: "..." }` 的渲染问题，Markdown 内容现按 Markdown 渲染而非 JSON 字符串；并增加 `raw !== null` 判断，避免 `null` 被当作对象处理

---

## MAARS v4.7.0 `v4.7.0`

*发布于 2026-03-01*

**发布日期**：2025-03-01

## 概述

新增 **Idea Agent**，支持从模糊研究想法中提取关键词并检索 arXiv 文献；三个 Agent（Idea / Plan / Task）的 Thinking 流式输出与 Output 区域职责已统一，并补充了工作流与区域职责文档。

## 新增功能 (Added)

- **Idea Agent**：Refine 按钮触发，LLM 流式提取关键词 → arXiv 检索 → 创建新 plan，支持 Mock 模式
- **API**：`POST /api/idea/collect`，请求体 `{idea, limit}`，返回 `{keywords, papers, planId}`
- **WebSocket**：`idea-thinking` 事件，流式展示关键词提取过程
- **Output**：统一使用 key `idea` 展示文献列表（keywords + papers）
- **文档**：`docs/agents-workflow.md`（三个 Agent 工作流）、`docs/region-responsibilities.md`（Thinking/Output 职责规划）

## 变更 (Changed)

- **三个 Agent**：`on_thinking` 回调统一使用 `await emit`，保证 thinking chunk 顺序与送达
- **Plan Agent**：executor 调整以支持统一 emit 流水线
- **Task Agent**：runner、agent、validation 支持 `idea-thinking` 与 Output key 规范
- **前端**：plan.js 支持 Refine 流程，websocket.js 监听 `idea-thinking`，thinking.js 支持 `source: 'idea'`
- **文档索引**：`docs/README.md` 更新为引用 `agents-workflow.md`

## 修复 (Fixed)

- Task Agent Mock 模式与 Plan/Idea 对齐，使用 `test/mock-ai/execute.json` 流式输出

---

## MAARS v4.7.1 `v4.7.1`

*发布于 2026-03-01*

**发布日期**：2025-03-01

## 概述

更新 README 文档，补充 Idea Agent、Refine 流程说明及项目结构，使文档与 v4.7.0 代码保持一致。

## 变更 (Changed)

- **README**：补充 Refine 按钮与 Idea Agent 说明
- **核心流程**：新增「0. Refine（可选）」步骤
- **Agent 工作流**：新增 Idea Agent 小节
- **项目结构**：加入 `idea_agent/` 及 `test/mock-ai/` 说明
- **文档**：新增文档索引链接
- **Thinking 区域**：展示阶段更新为 Refine/Plan/Execute

---

## MAARS v4.8.0 `v4.8.0`

*发布于 2026-03-01*

**发布日期**：2025-03-01

## 概述

本版本聚焦 Thinking 区域统一设计、Stop 流程优化与三 Agent 流程对称性，并完成前端模块化重构。**Idea Agent Refine 流程**与 Plan/Task 对齐：Keywords 与 Refine 均支持流式 thinking、abort_event 终止、prompt 鼓励 reasoning。调度信息统一为 header-only 结构，Stop 点击后立即恢复按钮并终止 LLM 调用，避免 token 浪费。

## 新增功能 (Added)

- **Thinking 区域**：调度信息统一为 thinking 块 header-only 结构，与有内容块共用 header 格式
- **文档**：新增 `docs/thinking-area-design.md`，说明 Thinking 区域设计、展示逻辑与 Prompt 约定
- **规则**：`agent-flow-architecture` 强调流程一致性与对称性，新增「常见不对称陷阱」检查清单

## 变更 (Changed)

- **Idea Agent Refine 流程**：Keywords 与 Refine 两阶段 prompt 统一鼓励「先 reasoning 再输出」，并说明「This will be shown as your thinking process」；Refine 支持 abort_event，Stop 后立即终止 LLM 调用；与 Plan/Task 保持流式 thinking、Stop 行为对称
- **Plan Agent**：atomicity、decompose、format、quality 统一为流式处理，移除非流式 reasoning 提取
- **Prompt**：Idea / Plan / Task 所有 prompt 统一鼓励「先 reasoning 再输出」
- **前端**：JS/CSS 模块化重构，flows、regions、ws 分层，CSS 按 core/components/regions/ui 拆分

## 修复 (Fixed)

- **Stop 按钮**：点击 Stop 后立即恢复按钮状态，不再等待后端 error 事件
- **Stop 终止**：Plan / Idea / Task 三 Agent 均支持 abort_event，Stop 后尽快终止 LLM 调用，减少 token 消耗
- **Idea Agent**：新增 abort_event 支持，Stop 后终止 Keywords / Refine 的 LLM 流
- **后端 Stop**：Plan / Task 的 stop 端点立即推送 error 事件，前端可更快恢复 UI

---

## MAARS v4.8.1 `v4.8.1`

*发布于 2026-03-01*

**发布日期**：2025-03-01

## 概述

Thinking 区域 header 分隔符由 `·` 改为 `|`，文档与实现保持一致。

## 变更 (Changed)

- **Thinking 区域**：Header 分隔符由 `·` 改为 `|`，提升可读性
- **文档**：`docs/thinking-area-design.md` 已同步更新

---

## MAARS v4.8.2 `v4.8.2`

*发布于 2026-03-01*

**发布日期**：2025-03-01

## 概述

移除 Load Idea 按钮，刷新页面时自动填充示例 idea，简化首次使用流程。

## 变更 (Changed)

- **Idea 输入**：移除 Load Idea 按钮，刷新页面自动填充示例 idea
- **Restore 兼容**：若有可恢复的 plan，restore 会覆盖为已保存的 idea
- **文档**：README 已同步更新

---

## MAARS v4.9.0 `v4.9.0`

*发布于 2026-03-01*

**发布日期**：2025-03-01

## 概述

本版本新增 Toast 轻量通知组件，支持操作反馈提示；Tree View 标签栏支持横向滚动，便于多标签场景；文档同步更新前端脚本依赖说明。

## 新增功能 (Added)

- **Toast 通知组件**：新增 `toast.success(msg)`、`toast.error(msg)`、`toast.warning(msg)`、`toast.info(msg)` API，左下角弹出，支持 success/error/warning/info 四种类型，与 MAARS 设计系统一致（边框、圆角、主题变量），支持 light/dark/black 模式

## 变更 (Changed)

- **Tree View**：Decomposition/Execution 标签栏支持横向滚动（`overflow-x: auto`），多标签时不再挤压布局
- **文档**：`docs/FRONTEND_SCRIPTS.md` 补充 toast.js 加载顺序与 `window.MAARS.toast` 说明

---

## MAARS v4.9.1 `v4.9.1`

*发布于 2026-03-01*

**发布日期**：2025-03-01

## 概述

本版本新增 `.gitattributes`，统一文本文件行尾为 LF，避免 Windows/Unix 换行符差异导致的虚假变更。

## 变更 (Changed)

- **行尾规范**：新增 `.gitattributes`（`* text=auto eol=lf`），仓库内文本文件统一使用 LF，跨平台协作时减少换行符相关 diff 与冲突

---

## MAARS v4.9.2 `v4.9.2`

*发布于 2026-03-01*

**发布日期**：2026-03-02

## 概述

README 文档更新：补充三 Agent 工作流程说明，以及 LLM / Agent 模式实现进度表，便于快速了解系统架构与各模式支持情况。

## 变更 (Changed)

- **README**：新增「三 Agent 工作流程」章节，说明统一流程模型（HTTP 触发 + WebSocket 回传）、各 Agent 职责与事件、Stop/thinking/error 行为
- **README**：新增「LLM / Agent 模式实现进度」表，列出 Idea / Plan / Task 的 LLM 与 Agent 模式实现状态，以及 AI Mode 与 Plan/Task 的对应关系
- **README**：项目结构中补充 `plan_agent/agent.py`、`task_agent/agent.py`，配置说明中补全 LLM+Agent 选项

---

## MAARS v4.10.0 `v4.10.0`

*发布于 2026-03-02*

**发布日期**：2026-03-02 23:00

## 概述

新增 Agent 自迭代能力（Self-Reflection）：三个 Agent 均可在任务完成后自动评估输出质量、生成可复用 skill 并按需重执行，持续提高执行质量。同时完善了 Idea Agent 的 ReAct 模式实现、Settings UI 重构为 Agent Mode 矩阵，并增强了 LLM 调用的超时与中止处理。

## 新增功能 (Added)

- **Self-Reflection 自迭代框架**：三个 Agent 完成主任务后自动进入反思循环——评估输出质量（LLM 评分）→ 生成 skill → 按需重执行。Idea Agent 评估新颖性/科研价值/可行性/研究空白，Plan Agent 评估 MECE/依赖/粒度/可执行性，Task Agent 评估完整性/深度/准确性/格式符合度
- **Learned Skills 持久化**：反思过程中生成的 skill 保存到各 Agent 的 `skills/` 目录，下次运行时 `ListSkills` 自动发现，实现跨 run 经验积累
- **Self-Reflection 配置 UI**：Settings → AI Config 面板新增 Self-Reflection 卡片，可配置开关、最大迭代次数（1-5）、质量阈值（0-100）
- **Idea Agent ReAct 模式**：完整工具链——ExtractKeywords → SearchArxiv → EvaluatePapers → FilterPapers → AnalyzePapers → RefineIdea → ValidateRefinedIdea → FinishIdea，支持 ListSkills/LoadSkill
- **Thinking 区域 Reflect 样式**：反思阶段 thinking 块带 accent 色左侧标记，通过 `data-operation="Reflect"` 与常规 thinking 区分
- **共享常量模块**：`shared/constants.py` 集中定义 Temperature、Agent 轮数、并发数、超时、Reflection 参数等

## 变更 (Changed)

- **Settings UI 重构**：Agent Mode 从独立模块合并进 `settings.js`，删除 `settings-mode-config.js`；新增 Agent Mode 矩阵（Mock/LLM/Agent × Idea/Plan/Task）
- **LLM 调用增强**：`shared/llm_client.py` 新增 `LLM_REQUEST_TIMEOUT` 超时（120s）和 `LLM_STREAM_CHUNK_TIMEOUT`（60s），非流式调用支持 abort_event 竞争取消，流式调用添加初始连接超时
- **merge_phase_config 简化**：移除 phase-specific override 逻辑，统一使用全局 API 配置
- **三 Agent on_thinking 签名对齐**：统一为 `(chunk, task_id, operation, schedule_info)` 格式
- **complete 事件扩展**：`idea-complete`、`plan-complete` 事件数据新增 `reflection` 字段（iterations、bestScore、skillsCreated）
- **DB 配置解析**：`_resolve_config()` 新增 `reflectionEnabled`、`reflectionMaxIterations`、`reflectionQualityThreshold` 配置映射
- **文档更新**：`agents-workflow.md` 新增 Self-Reflection 章节，operation 命名增加 `Reflect`；README 更新项目结构与配置说明

---

## MAARS v5.0.0 `v5.0.0`

*发布于 2026-03-03*

**发布日期**：2025-03-03

## 概述

本版本新增第四个 Agent（Paper Agent），支持根据 Plan 与 Task 产出生成论文草稿；同时完成三 Agent 架构重构，统一 ADK 桥接与 Skill 加载逻辑，并扩展 Idea Agent Skills。

## 新增功能 (Added)

- **Paper Agent**：根据 Plan 与 Task 产出生成论文草稿，支持 Markdown 格式；HTTP 触发、WebSocket 回传（paper-start / paper-thinking / paper-complete），与 Idea/Plan/Task 流程一致
- **Idea Agent Skills**：新增 keyword-extraction、literature-grounding、paper-evaluation、rag-research-template、refined-idea-quality、research-templates、topic-refinement 等 Skills
- **RAG 引擎**：`idea_agent/rag_engine.py` 支持文献检索与 RAG 模板
- **Agent 目录结构规范**：新增 `docs/agent-structure.md`，统一 Idea/Plan/Task 目录结构与 Skills 规范

## 变更 (Changed)

- **三 Agent 架构重构**：抽出 `shared/adk_bridge.py`，各 Agent 的 `adk_runner.py` 独立实现，统一 `create_executor_tools` 与 Skill I/O
- **skill_utils**：增强 `list_skills`、`load_skill`、`read_skill_file`，支持 references 与 scripts 路径解析
- **文档**：`agents-workflow.md` 补充 Paper Agent 工作流；`region-responsibilities.md` 补充 Output 区域 paper key 说明；README 更新为四 Agent 流程
- **前端**：Thinking 区域支持 `source: paper`；Output 区域支持 paper 产出；WebSocket 新增 paper 事件监听

---

## MAARS v5.1.0 `v5.1.0`

*发布于 2026-03-03*

**发布日期**：2025-03-03

## 概述

本版本为 Paper Agent 增加 Mock 模式，与 Idea/Plan/Task 保持一致；Settings 支持四 Agent 模式选择，Output 区域在 paper-start 时仅清空 paper 槽位。

## 新增功能 (Added)

- **Paper Agent Mock 模式**：支持 `paperUseMock`，从 `test/mock-ai/paper.json` 加载 mock，通过 mock_chat_completion 流式输出，与 Idea/Plan/Task 对齐
- **Settings 四 Agent 对称**：Paper Agent 增加 Mock/LLM/Agent 模式选择行，与 Idea/Plan/Task 一致

## 变更 (Changed)

- **配置**：`db/_resolve_config` 支持 `paperAgent`、`paperUseMock`、`paperAgentMode`
- **Output 区域**：`paper-start` 时仅清空 paper 槽位（`clearPaperOutput`），保留 task 产出
- **按钮文案**：Paper 按钮文案改为 Write
- **文档**：`agents-workflow.md`、`README.md`、`backend/README.md`、`frontend/js/flows/README.md` 更新 Paper Agent Mock 说明

---

## MAARS v5.2.0 `v5.2.0`

*发布于 2026-03-03*

**发布日期**：2025-03-03

## 概述

本版本将 Idea Agent 的 refined_idea 输出由固定 JSON 结构改为 Markdown 字符串，提升表达灵活性；Plan、Task、Reflection 等下游通过 `get_idea_text` 统一读取。

## 变更 (Changed)

- **refined_idea 格式**：由 `{description, research_questions, research_gap, method_approach}` 改为 Markdown 字符串，LLM 与 Agent 模式均直接输出 Markdown
- **shared/idea_utils**：新增 `get_idea_text(refined)`，供 Plan、Task、Reflection 从 refined_idea 提取文本
- **Plan / Task**：使用 `get_idea_text(refined_idea)` 替代 `refined.get("description")` 获取分解输入
- **Output 区域**：`formatRefineResult` 直接渲染 refined_idea 字符串；移除 `refine` 键迁移逻辑
- **Idea Agent Skills**：rag-research-template、refined-idea-quality、research-templates、topic-refinement 去掉固定 schema 映射，改为灵活 Markdown 输出
- **Mock 数据**：`refine-idea.json` 的 content 改为 Markdown 格式

## 技术细节 / 迁移指南

- 若数据库中已有旧格式 refined_idea（对象），Plan/Task 会回退到 raw_idea；建议重新执行 Refine 以使用新格式

---

## MAARS v5.3.0 `v5.3.0`

*发布于 2026-03-03*

**发布日期**：2025-03-03

## 概述

本版本重构文档结构，将工作流与设计文档拆分到 `workflow/` 与 `design/` 目录，并更新 README 中的流程与配置说明。

## 变更 (Changed)

- **文档结构**：`docs/agents-workflow.md` 拆分为 `workflow/`（user-flow、agents、events-and-modes）；`agent-structure`、`region-responsibilities`、`thinking-area-design` 移至 `design/`
- **docs/README.md**：更新文档索引，指向新目录
- **README.md**：Refine 创建 idea_id（非 plan）；Paper 按钮文案为 Write；db 路径为 `db/{idea_id}/{plan_id}/`；配置说明更新为 Theme、AI Config、Data
- **backend/README.md**：agent-structure 链接改为 `docs/design/agent-structure.md`
- **docs/FRONTEND_SCRIPTS.md**：内容更新

---

## MAARS v5.3.1 `v5.3.1`

*发布于 2026-03-03*

**发布日期**：2025-03-03

## 概述

本版本精简 README，使结构更清晰、内容更易读。

## 变更 (Changed)

- **README**：精简为约 87 行，移除冗余流程说明；保留快速开始、使用流程、四 Agent、配置、项目结构、文档索引；使用流程改为表格化；项目结构改为更简洁的树形展示

---

## MAARS v5.3.2 `v5.3.2`

*发布于 2026-03-03*

**发布日期**：2025-03-03

## 概述

本版本调整 README 的 Markdown 格式，以提升可读性和规范度。

## 变更 (Changed)

- **README**：URL 使用 `<http://...>` 格式；代码块使用 `text` 语言标识；表格使用 `| --- |` 分隔符；移除表格单元格内多余加粗

---

## MAARS v5.4.0 `v5.4.0`

*发布于 2026-03-04*

**发布日期**：2025-03-03

## 概述

本版本新增开发指南文档，并修正前端 Restore 流程与 Task 清空逻辑。

## 新增功能 (Added)

- **开发指南**：新增 `docs/DEVELOPMENT_GUIDE.md`，涵盖底层架构、四 Agent 流程、三模式、Skill 扩充与维护等

## 修复 (Fixed)

- **Task 流程**：`maars:task-start` 时调用 `clear()`，确保 Task 区域正确清空
- **Restore 流程**：Settings 中 Restore 成功后不再手动派发 `maars:idea-complete`、`maars:plan-complete`，由 `maars:restore-complete` 统一处理
- **plan-error**：WebSocket 转发时携带 `detail.error`，供前端使用

## 变更 (Changed)

- **文档索引**：README、docs/README 增加开发指南链接

---

## MAARS v5.5.0 `v5.5.0`

*发布于 2026-03-05*

**发布日期**：2025-03-03

## 概述

本版本引入会话隔离架构，支持多用户并发；并抽取 adk_runtime、realtime 等共享模块，简化 Agent 路由与 ADK 运行逻辑。

## 新增功能 (Added)

- **会话隔离**：按 `sessionId` 维护独立运行上下文；`POST /api/session/init` 签发 `sessionId + sessionToken`；WebSocket 通过 `auth.sessionId + auth.sessionToken` 进入 room；HTTP 通过 `X-MAARS-SESSION-ID + X-MAARS-SESSION-TOKEN` 绑定同一会话；事件按 room 定向发射；空闲会话按 TTL 自动回收（默认 7200 秒）
- **shared/adk_runtime**：统一 ADK Runner 生命周期、事件循环、中止控制、finish 解析，减少三个 adk_runner 重复逻辑
- **shared/realtime**：`build_thinking_emitter` 统一 thinking 事件 payload 组装，支持 room 定向
- **Settings 快捷键**：Mac 支持 Cmd+Shift+S

## 变更 (Changed)

- **API 路由**：idea、plan、paper、execution 均通过 session 获取 run state，thinking 事件按 room 发射
- **前端**：config 支持 session init；api 请求携带 session header；WebSocket 连接携带 session auth；各 flow 使用 session 绑定
- **文档**：backend/README、docs/design/agent-structure、docs/DEVELOPMENT_GUIDE 补充会话隔离与共享模块说明

---

## MAARS v5.6.0 `v5.6.0`

*发布于 2026-03-05*

**发布日期**：2025-03-03

## 概述

本版本新增左侧抽屉式 Sidebar，提供 Settings 快捷入口，并支持延迟渲染与过渡动画。

## 新增功能 (Added)

- **Sidebar**：左上角切换按钮打开左侧抽屉；内容延迟渲染，关闭时先隐藏再清空；内含 Settings 入口，点击可打开设置弹窗并关闭 Sidebar
- **Settings 开放接口**：`window.MAARS.settings.openSettingsModal()` 供 Sidebar 等模块调用

---

## MAARS v5.7.0 `v5.7.0`

*发布于 2026-03-14*

**发布日期**：2026-03-14

## 概述

本版本新增以 `Research` 为核心的主流程，引入 `SSE` 实时通信与 `SQLite` 持久化，并增强 `Task` 的 Docker 执行能力，同时整理了文档结构。

## 新增功能 (Added)

- **Research 工作流**：新增 `Research` 列表页、详情页，以及按阶段执行、继续、重试、停止能力
- **实时事件**：前端新增基于 `SSE / EventSource` 的实时事件流，用于同步会话与阶段状态
- **持久化存储**：新增 `SQLite` 存储后端，覆盖 ideas、plans、executions、research、papers 和 settings
- **Task 执行**：新增基于 Docker 的任务执行支持与运行时状态上报能力

## 修复 (Fixed)

- **阶段校验**：补充阶段前置条件检查，减少错误阶段流转
- **执行状态**：改善任务执行过程中的状态同步、恢复和清理行为
- **Research 删除**：删除研究时级联清理相关执行数据与产物

## 变更 (Changed)

- **主流程**：前端从分散的 Idea / Plan / Task / Paper 流程收敛为以 `Research` 为中心
- **实时通道**：前端默认实时通信切换为 `SSE / EventSource`，后端保留兼容层
- **Paper Agent**：文档与实现统一为 `outline -> sections -> assembly` 的 MVP 流程
- **文档结构**：精简重复文档，重组开发与工作流说明

## 说明

- 本次实际发布版本为 `v5.7.0`；相关发布提交信息中仍保留 `prepare v5.6.1` 的旧文案，但不影响实际 tag 与发布内容。

---

## MAARS v5.7.1 `v5.7.1`

*发布于 2026-03-14*

**发布日期**：2026-03-14

## 概述

本版本将“发版”流程沉淀为仓库内共享 skill，并同步收敛 Release Note 规范，方便团队成员在拉取仓库后直接按统一流程发布版本。

## 新增功能 (Added)

- **共享发版技能**：新增仓库级 `release-workflow` skill，路径为 `.codex/skills/release-workflow/`
- **技能入口**：新增根目录 `AGENTS.md`，声明本项目的共享 skill 与触发方式

## 修复 (Fixed)

- **协作发版**：修复发版流程只存在于个人本地环境中的问题，改为随仓库一起分发，降低多人协作时的使用门槛

## 变更 (Changed)

- **Release Note 规范**：`docs/RELEASE_NOTE_STANDARD.md` 调整为更适合 GitHub Release 首屏阅读的中文短版模板
- **文档索引**：README、docs/README、docs/DEVELOPMENT_GUIDE 增加仓库共享技能与发版入口说明

---

## MAARS v6.0.0 `v6.0.0`

*发布于 2026-03-19*

## MAARS v6.0.0 — Architecture Overhaul

### Backend: ExecutionRunner Rebuild

- **Zero mixin inheritance**: `ExecutionRunner` no longer inherits from 5 mixin classes. All behavior is composed via ~40 thin delegate methods forwarding to 5 focused function modules (`runner_retry`, `runner_memory`, `runner_scheduling`, `runner_orchestration`, `runner_phases`).
- **Dependency injection**: `RunnerDeps` dataclass replaces the `_runner_module()` lazy-import hack. All 25+ external dependencies are explicit and injectable. Tests use `RunnerDeps(xxx=fake)` instead of brittle monkeypatching.
- **God method decomposition**: The 490-line `_execute_task()` method is now 5 clear phase methods with a ~60-line orchestrator.
- **Mock mode separation**: Mock/LLM/Agent mode branching extracted from business logic in Plan and Idea agents.
- **Dead code cleanup**: Removed 16 backward-compat imports, 1 unused attribute (`task_failure_count`), duplicate `_env_float` definitions, and unused module imports.
- **File renaming**: Mixin files renamed to reflect their new roles (`runner_retry.py`, `runner_memory.py`, `runner_scheduling.py`, `runner_orchestration.py`, `runner_phases.py`).
- **Test migration**: All unit and API tests migrated from `monkeypatch.setattr(runner_mod, ...)` to proper `RunnerDeps` / `runner._deps` injection.

### Frontend: UX & Code Quality

- **Security**: SSE session credentials moved from URL query params to HttpOnly SameSite=Strict cookies.
- **UX**: All 21 `alert()` calls replaced with the existing toast notification system (`toast.error()` / `toast.warning()`).
- **Code quality**: All 33 inline `style.display` manipulations replaced with `el.hidden` attribute or CSS classes (`.is-open`). Zero inline styles remain in HTML/JS.
- **Module decomposition**: The 724-line `research-large-helpers.js` split into 3 focused modules: `research-execute-state.js` (235L), `research-loader.js` (181L), `research-event-bridges.js` (325L).

### Documentation

- Added `ARCHITECTURE.md` covering the full system design: four-agent pipeline, backend layered structure, Task Agent internals, frontend event-driven architecture, and key design decisions.

---

## MAARS v6.0.0 — 架构大重构

### 后端：ExecutionRunner 重建

- **零 Mixin 继承**：`ExecutionRunner` 不再继承 5 个 Mixin 类。所有行为通过 ~40 个薄代理方法转发到 5 个聚焦的函数模块（`runner_retry`、`runner_memory`、`runner_scheduling`、`runner_orchestration`、`runner_phases`）。
- **依赖注入**：`RunnerDeps` dataclass 替代了 `_runner_module()` 延迟导入 hack。25+ 个外部依赖全部显式可注入。测试直接使用 `RunnerDeps(xxx=fake)`，不再依赖 monkeypatch。
- **上帝方法拆分**：490 行的 `_execute_task()` 拆分为 5 个阶段方法 + ~60 行编排器。
- **Mock 模式分离**：Plan 和 Idea Agent 的 Mock/LLM/Agent 模式分支从业务逻辑中抽离。
- **死代码清理**：移除 16 个 backward-compat import、1 个废弃属性 (`task_failure_count`)、重复的 `_env_float` 定义和未使用的模块导入。
- **文件重命名**：Mixin 文件重命名以反映新角色（`runner_retry.py`、`runner_memory.py`、`runner_scheduling.py`、`runner_orchestration.py`、`runner_phases.py`）。
- **测试迁移**：所有 unit 和 API 测试从 `monkeypatch.setattr(runner_mod, ...)` 迁移到 `RunnerDeps` / `runner._deps` 注入。

### 前端：UX 与代码质量

- **安全**：SSE 会话凭证从 URL 参数移至 HttpOnly SameSite=Strict cookie。
- **UX**：21 个 `alert()` 调用全部替换为已有的 toast 通知系统（`toast.error()` / `toast.warning()`）。
- **代码质量**：33 处 `style.display` 内联操作替换为 `el.hidden` 属性或 CSS class（`.is-open`）。HTML/JS 中零内联样式。
- **模块拆分**：724 行的 `research-large-helpers.js` 拆分为 3 个聚焦模块：`research-execute-state.js`（235 行）、`research-loader.js`（181 行）、`research-event-bridges.js`（325 行）。

### 文档

- 新增 `ARCHITECTURE.md`，覆盖完整系统设计：四 Agent 管道、后端分层结构、Task Agent 内部架构、前端事件驱动架构及关键设计决策。

---

## v7.0.0-pre.1 — Pipeline Architecture Overhaul `v7.0.0-pre.1`

*发布于 2026-03-22*

## What changed

Major backend restructuring: unified LLM pipeline, mock system, and agent architecture.

### New modules

- **`llm/`** — Unified single-round LLM layer
  - Two entry points: `llm_call` (text) and `llm_call_structured` (parsed data with retry)
  - Native Gemini interface (removed OpenAI compatibility layer)
  - 12 prompt templates in `llm/prompts/{agent}-{action}.txt`
  - Output format converged to explicit `type: "json" | "markdown"`

- **`mock/`** — Unified mock runtime
  - `load_mock()` single interface, `mock/data/` for all JSON fixtures
  - Mock injected via `mock=` parameter — zero branching in function bodies

- **`adk/`** — Unified ADK agent runner
  - `run_agent()` absorbs boilerplate from all 4 agent runners
  - Pure agent mode: removed nested LLM tool calls (Idea: 11→6, Plan: 11→8, Paper: 7→4 tools)
  - Idea/Plan/Paper agents fully decoupled from `llm/` layer

### Paper Agent
- Structurally aligned with other 3 agents (new adk_runner, agent_tools, tool_schemas, prompts)

### Deleted
- `shared/llm_client.py`, `shared/mock_utils.py`, `shared/structured_output.py`
- `{agent}/llm/` directories (moved to `llm/`)
- `test/` directory (moved to `mock/`)
- OpenAI format conversion functions
- 11 redundant nested-LLM agent tools

### Stats
- 68 files changed, +1,908 / −2,727 lines (net −819)

### Next: Task Agent simplification (not yet implemented)

The current Task Agent `adk_runner.py` (296 lines) stuffs all inputs into the initial prompt, then uses LLM to compress when it overflows. This is backwards — the agent has `ReadArtifact` / `ReadFile` tools and should fetch data on demand.

Target state:
```python
async def run_task_agent_adk(task_id, description, output_spec, api_config, ...):
    prompt = load_prompt("task_agent", "task-agent-prompt.txt")
    user_message = f"**Task:** {description}
**Output format:** ..."
    finish_result, _ = await run_agent(name="task", prompt=prompt, ...)
    return finish_result
```

What to remove:
- `_compress_object_with_llm` (106 lines) — agent reads inputs via tools instead
- `adk_prompt.py` (238 lines) — replaced by a prompt file + concise user message
- Pre-packed resolved_inputs, execution_context, retry_memory in prompt — agent fetches as needed

This would bring Task Agent in line with the other three (< 80 lines).

---

<details>
<summary>中文</summary>

## 变更内容

后端大规模架构重构：统一 LLM 管道、Mock 系统和 Agent 架构。

### 新模块

- **`llm/`** — 统一单轮 LLM 层
  - 两个入口：`llm_call`（返回文本）和 `llm_call_structured`（解析数据 + 重试）
  - 原生 Gemini 接口（移除 OpenAI 兼容层）
  - 12 个 prompt 模板，统一命名 `llm/prompts/{agent}-{action}.txt`
  - 输出格式收敛为显式 `type: "json" | "markdown"`

- **`mock/`** — 统一 Mock 运行时
  - `load_mock()` 唯一加载接口，`mock/data/` 存放所有 JSON 数据
  - 通过 `mock=` 参数注入 — 函数体内零分支

- **`adk/`** — 统一 ADK Agent 运行器
  - `run_agent()` 吸收 4 个 agent runner 的公共模板代码
  - 纯 Agent 模式：移除嵌套 LLM 工具调用（Idea: 11→6, Plan: 11→8, Paper: 7→4 工具）
  - Idea/Plan/Paper Agent 与 `llm/` 层彻底解耦

### Paper Agent
- 目录结构与其他 3 个 Agent 对齐（新增 adk_runner, agent_tools, tool_schemas, prompts）

### 删除
- `shared/llm_client.py`、`shared/mock_utils.py`、`shared/structured_output.py`
- `{agent}/llm/` 目录（迁移至 `llm/`）
- `test/` 目录（迁移至 `mock/`）
- OpenAI 格式转换函数
- 11 个冗余的嵌套 LLM Agent 工具

### 统计
- 68 个文件变更，+1,908 / −2,727 行（净删 819 行）

### 下一步：Task Agent 简化（尚未实施）

当前 Task Agent 的 `adk_runner.py`（296 行）把所有输入塞进初始 prompt，塞不下就用 LLM 压缩。这是反模式 — Agent 明明有 `ReadArtifact` / `ReadFile` 工具，应该按需读取数据。

目标状态：
```python
async def run_task_agent_adk(task_id, description, output_spec, api_config, ...):
    prompt = load_prompt("task_agent", "task-agent-prompt.txt")
    user_message = f"**Task:** {description}
**Output format:** ..."
    finish_result, _ = await run_agent(name="task", prompt=prompt, ...)
    return finish_result
```

要删除的：
- `_compress_object_with_llm`（106 行）— Agent 通过工具按需读取输入
- `adk_prompt.py`（238 行）— 替换为 prompt 文件 + 简洁的 user message
- prompt 中预塞的 resolved_inputs、execution_context、retry_memory — Agent 按需获取

完成后 Task Agent 将与其他三个对齐（< 80 行）。

</details>

---

## MAARS 8.0.0 `v8.0.0`

*发布于 2026-03-23*

## MAARS 8.0.0 — Complete Rewrite: Multi-Mode Research Pipeline

From a single idea to a complete research paper, fully automated. Three modes, four stages, one unified architecture.

```bash
git clone https://github.com/dozybot001/MAARS.git
cd MAARS && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # add your API key
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### Highlights

**Three execution modes** — Mock (data replay for dev), Gemini (direct LLM calls), Agent (Google ADK with ReAct loops). Switch with one env var: `MAARS_LLM_MODE=agent`.

**Four-stage pipeline** — Refine (explore→evaluate→crystallize) → Plan (recursive decomposition with dependency DAG) → Execute (parallel batch execution with verification) → Write (outline→sections→polish).

**Unified streaming model** — Every LLM call emits `call_id`-tagged chunks. Frontend routes to per-call DOM blocks. Parallel tasks stream without interleaving.

**Three-layer architecture** — `llm/` (interface) → `pipeline/` (framework) → `mode/` (mock|gemini|agent). Pipeline never knows which mode is active. Zero coupling.

**File-based research DB** — Each run creates a timestamped folder with idea, refined idea, plan tree, task outputs, and final paper.

**Dual-panel frontend** — Left: LLM output log with collapsible stages. Right: decomposition tree, execution progress, file icons for outputs. Vanilla JS, zero build step.

### Showcase

Two complete research runs included:

| Mode | Topic | Tasks |
|------|-------|-------|
| Gemini | Cognitive Buffer Hypothesis — cultural modulation of news framing | 31 |
| Agent | HMAO — adversarial multi-agent role specialization | 12 |

Build process documented via [Intent](https://github.com/dozybot001/Intent) semantic history (8 snaps + 3 decisions).

---

<details>
<summary>中文</summary>

## MAARS 8.0.0 — 完全重写：多模式研究管线

从一个想法到一篇完整论文，全自动。三种模式、四个阶段、一套统一架构。

```bash
git clone https://github.com/dozybot001/MAARS.git
cd MAARS && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # 填入你的 API key
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 亮点

**三种执行模式** — Mock（开发用数据回放）、Gemini（直接 LLM 调用）、Agent（Google ADK + ReAct 循环）。一个环境变量切换：`MAARS_LLM_MODE=agent`。

**四阶段管线** — 精炼（探索→评估→结晶）→ 规划（递归分解 + 依赖 DAG）→ 执行（并行批次 + 验证）→ 写作（大纲→章节→润色）。

**统一流式模型** — 每次 LLM 调用发射带 `call_id` 标记的 chunk，前端按 call_id 路由到独立 DOM 块，并行任务互不干扰。

**三层架构** — `llm/`（接口）→ `pipeline/`（框架）→ `mode/`（mock|gemini|agent）。管线层完全不知道当前模式，零耦合。

**文件 DB** — 每次运行创建带时间戳的文件夹，保存想法、精炼结果、分解树、任务输出和最终论文。

**双栏前端** — 左侧：LLM 输出日志，阶段可折叠。右侧：分解树、执行进度、产出文件图标。纯 JS，零构建步骤。

### 展示

包含两次完整研究运行。构建过程通过 [Intent](https://github.com/dozybot001/Intent) 语义历史记录（8 个 snap + 3 个 decision）。

</details>

---

## v8.1.0 `v8.1.0`

*发布于 2026-03-25*

## MAARS 8.1.0 — Agent Architecture, Checkpoint Resume, Docker Reproduction

46 commits since v8.0.0. Agent mode goes from prototype to production-ready: unified streaming, MCP tooling, dedicated stages, checkpoint resume, and auto-generated Docker reproduction.

### Agent Mode

- **Unified AgentClient adapter** — Agent wraps ADK ReAct loop into `LLMClient.stream()`, same interface as Gemini/Mock. Pipeline never knows which mode is active.
- **Dedicated Refine/Write stages** — Single-session Agent stages replace multi-round pipeline orchestration. Agent self-directs research and writing.
- **Real-time streaming** — SSE `StreamingMode` delivers Think/Tool/Result events live to the UI.
- **MCP-first tool strategy** — Replaced custom search/fetch tools with ADK built-ins (`google_search`, `code_execute`) + MCP servers. Custom tools reserved for internal DB access only.
- **MCP failure resilience** — If MCP tools fail at runtime, Agent retries without them. MCP server failures no longer crash tasks.
- **Stop control** — `request_stop()` breaks the ReAct loop after the current event for clean interruption.

### Checkpoint Resume

- **Stop** cancels the stage task — no partial results saved to DB.
- **Resume** restarts `run()` — Execute loads completed tasks from `tasks/*.md` and skips them. Other stages restart from scratch (single-session, no checkpoint concept).
- **Retry** clears DB task files (`db.clear_tasks()`) for a clean restart. Downstream stages reset automatically.
- `stop_stage` / `resume_stage` are now async with proper task cancellation.

### Docker Reproduction

- **Auto-generated** after Execute stage: `Dockerfile.experiment` + `run.sh` + `docker-compose.yml`.
- `docker compose up` re-runs all experiments from a completed research session.
- `code_execute` tool runs Python in Docker containers, artifacts saved to `artifacts/`.

### Reasoning Log UX

- **Real token counts** — `usage_metadata` from Gemini API replaces `chars/2` heuristic. Both GeminiClient and AgentClient broadcast per-call token usage via SSE.
- **Auto-fold labels** — New Think/Tool/Result block auto-folds all previous blocks. Only the active block stays expanded. Click any label to toggle.
- **User-expanded protection** — Manually opened blocks/stages won't be auto-folded. Consistent at both stage and label level.

### Architecture & Quality

- **DB-only inter-stage communication** — Stages read/write through file DB, no `stage.output` string passing.
- **Broadcast split** — `has_broadcast` flag: Agent emits own chunks, pipeline emits for Gemini/Mock.
- **Code audit** — Fixed 3 critical + 5 high code smells from full audit.
- **Prompt engineering** — Removed artificial constraints from Plan, improved prompts across all stages, Agent instructions independent from pipeline prompts.

### Showcase

| Mode | Topic | Tasks |
|------|-------|-------|
| Agent | ODE Numerical Solvers — accuracy, stability, and computational efficiency | 22 |

---

<details>
<summary>中文</summary>

## MAARS 8.1.0 — Agent 架构、断点续跑、Docker 复现

自 v8.0.0 以来 46 个 commit。Agent 模式从原型走向生产：统一流式、MCP 工具链、专用 stage、断点续跑、自动 Docker 复现。

### Agent 模式

- **统一 AgentClient 适配器** — Agent 将 ADK ReAct 循环封装为 `LLMClient.stream()` 接口，与 Gemini/Mock 一致。Pipeline 层完全不知道当前模式。
- **专用 Refine/Write 阶段** — 单 session Agent stage 替代多轮 pipeline 编排，Agent 自主完成研究和写作。
- **实时流式** — SSE `StreamingMode` 将 Think/Tool/Result 事件实时推送到 UI。
- **MCP 优先工具策略** — 用 ADK 内置工具（`google_search`、`code_execute`）+ MCP server 替代自建工具。自建仅限内部 DB 访问。
- **MCP 容错** — MCP 工具运行时失败则去掉 MCP 重试。MCP server 故障不再导致任务崩溃。
- **Stop 控制** — `request_stop()` 在当前 ReAct event 后 break，干净中断。

### 断点续跑

- **Stop** 取消 stage task — 不产生不完整结果。
- **Resume** 重启 `run()` — Execute 从 `tasks/*.md` 加载已完成任务并跳过，只跑剩余。其他 stage 从头重跑（单 session 无 checkpoint）。
- **Retry** 清空 DB task 文件（`db.clear_tasks()`），完全重跑。下游 stage 自动重置。
- `stop_stage` / `resume_stage` 改为 async，支持正确的 task 取消。

### Docker 复现

- Execute 阶段结束后**自动生成** `Dockerfile.experiment` + `run.sh` + `docker-compose.yml`。
- `docker compose up` 即可重跑所有实验。
- `code_execute` 工具在 Docker 容器中运行 Python，产物保存到 `artifacts/`。

### 推理日志 UX

- **真实 Token 计数** — 用 Gemini API 的 `usage_metadata` 替代 `chars/2` 估算。GeminiClient 和 AgentClient 均通过 SSE 广播每次调用的 token 用量。
- **自动折叠** — 新 Think/Tool/Result 块出现时自动折叠之前所有块，只保持当前活跃块展开。点击标签可手动切换。
- **用户展开保护** — 手动打开的块/阶段不会被自动折叠。stage 级和 label 级逻辑统一。

### 架构与质量

- **阶段间仅通过 DB 通信** — 不再传递 `stage.output` 字符串。
- **广播分离** — `has_broadcast` 标志：Agent 自行发射 chunk，Gemini/Mock 由 pipeline 发射。
- **代码审计** — 修复 3 个 CRITICAL + 5 个 HIGH 坏味道。
- **Prompt 工程** — 移除 Plan 人为约束，改进所有阶段 prompt，Agent instruction 独立于 pipeline prompt。

### 展示

| 模式 | 主题 | 任务数 |
|------|------|-------|
| Agent | ODE 数值求解器 — 精度、稳定性与计算效率对比 | 22 |

</details>

---

## v9.0.0: Agno-Only Architecture + Strategy Phase `v9.0.0`

*发布于 2026-03-29*

## MAARS 9.0.0 — Agno-Only Architecture + Strategy Phase + New UI

Major architectural simplification: single adapter, smarter evaluation, new UI. Deleted ~1600 lines, added Strategy phase and score-based iteration control.

### Architecture: Agno-Only

- Removed ADK, Gemini, Mock modes — Agno is the sole LLM adapter
- AgnoClient is now a pure adapter (no baked-in instructions)
- All prompts flow from pipeline → AgnoClient via system messages
- ~1600 lines of dead code deleted

### New: Strategy Phase

- Agent researches best approaches (top solutions, key techniques) before task decomposition
- Strategy document injected into decompose prompt to guide task planning
- Progress bar: Refine → Calibrate → **Strategy** → Decompose → Execute → Evaluate → Write

### Improved Evaluation

- **System-level score tracking**: reads `best_score.json`, stops when score plateaus (<0.5% improvement)
- **LLM evaluation**: analyzes results with tools (reads full task outputs + artifacts), suggests specific improvements
- Separated concerns: system decides "keep going?", LLM decides "what to improve"

### New UI

- Slim progress bar with 7 phase nodes (replaces stage cards)
- Command palette (Cmd+K / Ctrl+K): input + Start / Pause / Resume
- Reasoning Log organized by collapsible session groups
- Elapsed timer + copy buttons on both panels
- Workspace fills viewport

### Bug Fixes

- **Redecompose dependency fix**: downstream tasks now correctly wait for all subtasks (was skipping due to broken DAG)
- **Redecompose tree fix**: sub-decompose no longer overwrites the main plan tree
- Removed Kaggle auto-submit (manual only — avoids daily limit)

### DB Persistence

- `calibration.md`, `strategy.md` persisted to DB (resume-safe)
- All research state survives pause/resume

### Showcase

| Topic | Best CV | Kaggle Public |
|-------|---------|---------------|
| Titanic | 0.85 accuracy | — |
| House Prices | 0.1085 RMSLE | 0.1241 |

**Full Changelog**: https://github.com/dozybot001/MAARS/compare/v8.2.0...v9.0.0

---

<details>
<summary>中文</summary>

## MAARS 9.0.0 — Agno-Only 架构 + Strategy 阶段 + 全新 UI

重大架构精简：单一适配器、更智能的评估、全新 UI。删除约 1600 行代码，新增 Strategy 阶段和基于分数的迭代控制。

### 架构：Agno-Only

- 移除 ADK、Gemini、Mock 模式 — Agno 为唯一 LLM 适配器
- AgnoClient 现为纯适配器（不再内置 instruction）
- 所有 prompt 由 pipeline 通过 system message 传递给 AgnoClient
- 删除约 1600 行死代码

### 新增：Strategy 阶段

- Decompose 之前，Agent 用搜索工具调研最佳方案（高分方案、关键技巧）
- 策略文档注入 decompose prompt，指导任务规划
- 进度条：Refine → Calibrate → **Strategy** → Decompose → Execute → Evaluate → Write

### 改进评估

- **系统级分数追踪**：读取 `best_score.json`，分数不再提升时（<0.5%）自动停止
- **LLM 评估**：带工具分析实际结果（读取完整 task 输出 + artifacts），给出具体改进建议
- 职责分离：系统决定"是否继续"，LLM 决定"改进什么"

### 全新 UI

- 窄进度条，7 个阶段节点（替代 stage 卡片）
- 命令面板（Cmd+K / Ctrl+K）：输入框 + Start / Pause / Resume
- Reasoning Log 按 session 分组折叠（Calibrate、Strategy、Task 各自独立）
- 计时器 + 两侧 Copy 按钮
- 工作区占满视口

### Bug 修复

- **Redecompose 依赖修复**：下游任务现在正确等待所有子任务完成（之前因 DAG 断裂而跳过）
- **Redecompose 树修复**：子分解不再覆盖主分解树
- 移除 Kaggle 自动提交（改为手动，避免每日限额）

### DB 持久化

- `calibration.md`、`strategy.md` 持久化到 DB（resume 安全）
- 所有研究状态均可断点续跑

### 展示

| 题目 | 最佳 CV | Kaggle Public |
|------|---------|---------------|
| Titanic | 0.85 accuracy | — |
| House Prices | 0.1085 RMSLE | 0.1241 |

</details>

---

## v10.0.0: Architecture Overhaul — Unified Labels, Structured UI, I/O Centralization `v10.0.0`

*发布于 2026-03-29*

## MAARS 10.0.0 — Architecture Overhaul

Unified label system, structured right panel, centralized file I/O, streaming consolidation. Net -700 lines while adding significant new capabilities.

### Unified Chunk Level System

- Every chunk carries `level` field: 1=stage, 2=phase, 3=task/sub-session, 4=tool
- Backend emitters annotate level explicitly — frontend switches on it, no heuristics
- Eliminated hardcoded `SESSION_LABELS` set and all string-matching detection
- Tool call lifecycle fixed: `tool_call` creates fold, `tool_result` appends to same block

### Unified Fold UI

- Single CSS system: `.fold-label` / `.fold-body` / `.fold-text` for all levels
- Both panels use identical classes — differentiation by DOM nesting only
- Left panel: stage → phase → task → tool (all collapsible, auto-collapse on new sibling)
- Right panel: stage → phase → structured content (doc cards, tree, exec list, score)
- Global monospace font

### Structured Right Panel

- `doc:ready` event: clickable file cards for Refined Idea, Calibration, Strategy, Evaluation, Paper
- `score:update` event: visual score indicator with improved/declined styling
- Task completion includes summary — click task node to view in modal
- Modal component replaces `window.open()`

### Plan Sync

- `plan.json` → `plan_list.json` (symmetric with `plan_tree.json`)
- Amendment and redecompose update both files atomically
- `replan_tree` incremental SSE event removed — full tree push on mutation

### Kaggle Flow Fix

- `idea.md` stores user's raw input (URL + notes)
- `refined_idea.md` built from Kaggle API metadata + `data_description.txt` + `sample_submission.csv` + train data shape (~40x richer)
- Kaggle detection moved from route to `orchestrator.start()` — single entry point
- Friendly error when competition not joined (403 → "Please accept rules" with link)

### File I/O Centralization

- All file writes go through `db.py` — docker_exec and reproduce only call save methods
- `save_script()`, `promote_best_score()`, `save_reproduce_files()` on ResearchDB
- `get_root()` removed — internal paths no longer exposed
- `meta.json` replaces `score_direction.txt`

### Results Directory

- Per-task artifacts: `artifacts/{task_id}/001.py` with sequential naming
- Docker mounts: `/workspace/output/` per-task (rw), `/workspace/artifacts/` shared (ro)
- `best_score.json` auto-promoted from task dir to artifacts root
- Reproduce files in `reproduce/` subdirectory

### Streaming Consolidation

- `_stream_llm` lifted to BaseStage — Refine, Write, Research all use one method
- `evaluate.py` merged into ResearchStage (was a thin wrapper around one LLM call)
- `decompose.py` accepts `stream_fn` callable — no more duplicate streaming loops
- `prompts.py` extracted (207 lines of prompt constants + message builders)
- `_dispatch_stream` inlined into `_stream_llm` — one function, LLM stream to SSE

### UI Polish

- Button state machine: at most one button enabled (Start/Pause/Resume)
- Docker status indicator with 30s polling
- Docker pre-flight check before Execute phase
- Text blocks appear in chronological order (new block after tool fold, not appended to top)

**Full Changelog**: https://github.com/dozybot001/MAARS/compare/v9.0.0...v10.0.0

---

<details>
<summary>中文</summary>

## MAARS 10.0.0 — 架构大修

统一标签体系、结构化右侧面板、文件 I/O 集中管理、streaming 整合。净减 ~700 行代码，同时新增大量能力。

### 统一 Chunk Level 体系

- 每个 chunk 携带 `level` 字段：1=stage, 2=phase, 3=task/sub-session, 4=tool
- 后端显式标注 level，前端按 level switch 处理，消除所有启发式匹配
- 删除硬编码 `SESSION_LABELS` 集合
- 修复工具调用生命周期：`tool_call` 建折叠，`tool_result` 写入同一个 block

### 统一折叠 UI

- 三个 CSS class 替代 7+ 个旧 class：`.fold-label` / `.fold-body` / `.fold-text`
- 两侧面板完全相同的样式，靠 DOM 嵌套缩进区分层级
- 左侧：stage → phase → task → tool（全部可折叠，新建时自动折叠前一个）
- 右侧：stage → phase → 结构化内容（文件卡片、分解树、执行图、分数）
- 全局 monospace 字体

### 右侧结构化面板

- `doc:ready` 事件：Refined Idea / Calibration / Strategy / Evaluation / Paper 显示为可点击文件卡片
- `score:update` 事件：分数指示器，绿色（提升）/ 黄色（停滞）
- Task 完成时附带 summary，点击弹出 modal 查看
- Modal 组件替代 `window.open()`

### Plan 同步

- `plan.json` → `plan_list.json`（与 `plan_tree.json` 对称）
- Amendment 和 redecompose 同时更新两个文件
- 删除 `replan_tree` 增量 SSE 事件，改为完整 tree 推送

### Kaggle 流程修复

- `idea.md` 存用户原始输入（URL + 备注）
- `refined_idea.md` 从 Kaggle API + `data_description.txt` + `sample_submission.csv` 构建（信息量 ~40 倍）
- Kaggle 检测从 route 移入 `orchestrator.start()`
- 未 join 竞赛时友好报错（403 → 提示 accept rules 链接）

### 文件 I/O 集中

- 所有文件写入通过 `db.py`，docker_exec 和 reproduce 只调 save 方法
- 新增 `save_script()`、`promote_best_score()`、`save_reproduce_files()`
- 删除 `get_root()` 暴露
- `meta.json` 替代 `score_direction.txt`

### Results 目录

- 按 task 隔离：`artifacts/{task_id}/001.py` 顺序编号
- Docker 挂载：`/workspace/output/` 按 task（rw），`/workspace/artifacts/` 共享（ro）
- `best_score.json` 自动从 task 目录提升到 artifacts 根
- 复现文件移入 `reproduce/` 子目录

### Streaming 整合

- `_stream_llm` 提升到 BaseStage — Refine/Write/Research 共用
- `evaluate.py` 合入 ResearchStage
- `decompose.py` 通过 `stream_fn` callable 调用，不再有独立 streaming loop
- `prompts.py` 提取 207 行 prompt 常量
- `_dispatch_stream` 内联到 `_stream_llm` — 一个函数从 LLM 流到 SSE

### UI 细节

- 按钮状态机：同一时刻最多一个按钮可用
- Docker 状态指示灯（30 秒轮询）
- Execute 前 Docker 预检
- 文本块按时间顺序排列（工具折叠后新建 block，不追加到顶部）

</details>

---

## v11.0.0: Multi-Agent Refine & Write — TeamStage Architecture `v11.0.0`

*发布于 2026-03-30*

## MAARS 11.0.0 — Multi-Agent Refine & Write

Refine and Write stages are now **true multi-agent**: each uses an Agno Team in coordinate mode with two collaborating agents. Research remains an agentic workflow. A new `TeamStage` base class unifies all multi-agent execution logic.

### Multi-Agent Refine: Explorer + Critic

Refine is no longer a single-agent session. Two agents collaborate via Agno Team:
- **Explorer**: has search tools (DuckDuckGo, arXiv, Wikipedia), surveys literature, proposes research directions
- **Critic**: evaluates proposals for novelty, feasibility, and impact — pushes for stronger formulations
- Team leader orchestrates: Explorer → Critic → Explorer (revise based on feedback)

### Multi-Agent Write: Writer + Reviewer

Write follows the same pattern:
- **Writer**: has DB tools + search tools, reads all task outputs and writes the paper
- **Reviewer**: critically reviews the draft for structure, completeness, depth, and accuracy
- Team leader orchestrates: Writer → Reviewer → Writer (revise based on feedback)

### TeamStage Base Class

Both Team stages share a single `TeamStage(Stage)` base class (`backend/team/stage.py`) that provides:
- Generic `run()` loop: create team → stream events → capture primary member output → finalize
- Generic `_handle_event()`: maps Agno Team/member events to MAARS SSE
- Configurable via `_member_map` and `_capture_member` — subclasses are ~75 lines of config each

### Class Hierarchy

```
Stage                          — lifecycle + SSE (all stages)
├── AgentStage                 — single-client workflow (AgnoClient)
│   └── ResearchStage          — decompose → execute → evaluate → replan
└── TeamStage                  — multi-agent (Agno Team coordinate)
    ├── RefineStage            — Explorer + Critic
    └── WriteStage             — Writer + Reviewer
```

### Removed: `llm/` Abstraction Layer

- Deleted `backend/llm/` entirely — `LLMClient` abstract class removed (only Agno exists)
- `AgnoClient` + `StreamEvent` moved to `backend/agno/client.py`
- `AgnoClient` is now only used by ResearchStage

### Codebase Structure

```
backend/
├── pipeline/          # Orchestration + Agentic Workflow (Research)
├── team/              # Multi-Agent stages (Refine + Write)
├── agno/              # Shared Agno infrastructure (client, models, tools)
└── ...
```

The three stages communicate **only through the file-based session DB** — fully decoupled. `pipeline/` doesn't know `team/` exists, and vice versa.

### Docs

- README + README_CN rewritten with dual architecture diagrams (data flow + system layers)
- `docs/CN/architecture.md` fully updated — reflects implemented multi-agent state
- `plans/write-multi-agent.md` archived (implemented)

**Full Changelog**: https://github.com/dozybot001/MAARS/compare/v10.0.0...v11.0.0

---

<details>
<summary>中文</summary>

## MAARS 11.0.0 — 多智能体精炼与写作

精炼和写作阶段升级为**真正的多智能体协作**：每个阶段使用 Agno Team coordinate 模式，两个 agent 协同工作。研究阶段保持 agentic workflow 不变。新增 `TeamStage` 基类统一所有多智能体执行逻辑。

### 多智能体精炼：Explorer + Critic

精炼阶段不再是单 agent session，而是两个 agent 通过 Agno Team 协作：
- **Explorer**：有搜索工具（DuckDuckGo, arXiv, Wikipedia），调研文献、提出研究方向
- **Critic**：评估提案的新颖性、可行性和影响力，推动更强的表述
- Team leader 编排：Explorer → Critic → Explorer（基于反馈修订）

### 多智能体写作：Writer + Reviewer

写作阶段同样模式：
- **Writer**：有 DB 工具 + 搜索工具，读取所有任务产出并写论文
- **Reviewer**：从结构、完整性、深度、准确性等维度审查初稿
- Team leader 编排：Writer → Reviewer → Writer（基于反馈修订）

### TeamStage 基类

两个 Team 阶段共享 `TeamStage(Stage)` 基类（`backend/team/stage.py`），提供：
- 通用 `run()` 循环：创建 team → 流式事件 → 捕获主 agent 输出 → 持久化
- 通用 `_handle_event()`：Agno Team/member 事件映射到 MAARS SSE
- 通过 `_member_map` 和 `_capture_member` 配置——子类仅 ~75 行配置代码

### 类继承

```
Stage                          — 生命周期 + SSE（所有阶段）
├── AgentStage                 — 单 Client workflow（AgnoClient）
│   └── ResearchStage          — 分解 → 执行 → 评估 → 重规划
└── TeamStage                  — 多 Agent 协作（Agno Team coordinate）
    ├── RefineStage            — Explorer + Critic
    └── WriteStage             — Writer + Reviewer
```

### 删除：`llm/` 抽象层

- 完整删除 `backend/llm/` 目录——`LLMClient` 抽象类移除（只有 Agno）
- `AgnoClient` + `StreamEvent` 迁入 `backend/agno/client.py`
- `AgnoClient` 现在仅被 ResearchStage 使用

### 代码结构

```
backend/
├── pipeline/          # 编排 + Agentic Workflow（Research）
├── team/              # 多智能体阶段（Refine + Write）
├── agno/              # 共享 Agno 基础设施（client, models, tools）
└── ...
```

三个阶段**仅通过文件型会话 DB 通信**——完全解耦。`pipeline/` 不知道 `team/` 的存在，反之亦然。

### 文档

- README + README_CN 重写，新增双架构图（数据流 + 系统层次）
- `docs/CN/architecture.md` 全面更新，反映已实现的多智能体状态
- `plans/write-multi-agent.md` 归档（已实施）

</details>

---

## v11.1.0: Security Hardening, Session Management, Vue 3 Migration `v11.1.0`

*发布于 2026-03-31*

## MAARS 11.1.0 — Security Hardening, Session Management, Vue 3 Migration

System-level improvements only — zero business logic changes. Security audit fixes, session management, frontend framework migration, CI hardening, and documentation overhaul.

### Security Hardening

- **SSE auth**: moved from URL query param (`?token=`) to `Authorization` header via `fetch` + `ReadableStream` — prevents token leakage to server logs, browser history, and monitoring
- **Page unload**: `sendBeacon` replaced with `fetch(..., { keepalive: true, headers })` for secure token handling
- **Query param fallback removed**: backend middleware no longer accepts `?token=`, only `Authorization: Bearer`
- **Startup warning**: prints yellow WARNING when `MAARS_API_KEY` is not set

### Session Management

- Session history API: `GET /api/sessions`, `GET /api/sessions/{id}/state`, `DELETE /api/sessions/{id}`
- Full frontend state restore from DB files — zero additional persistence needed
- Session drawer sidebar: browse, restore, and delete past sessions
- `beforeunload` auto-pause + checkpoint resume from DB artifacts

### Frontend: Vue 3 Migration

- Migrated from vanilla JS to **Vue 3 + Pinia + Vite**
- Command palette merged into ProgressBar component
- Session drawer component added

### CI & Infrastructure

- CI now validates frontend build (`npm ci && npm run build`)
- Per-stage model configuration: `MAARS_{STAGE}_PROVIDER` / `MAARS_{STAGE}_MODEL`
- File DB: atomic writes with `os.replace()`, thread-safe locking
- Test coverage expanded to **120 tests**

### Cleanup

- Removed dead `backend/pipeline/write.py` (308 lines, zero references)
- Removed `best_score.json` backward-compat fallback in research
- Removed unused outline/section DB methods and frontend phase labels
- README, README_CN, and `docs/CN/architecture.md` fully rewritten

**Full Changelog**: https://github.com/dozybot001/MAARS/compare/v11.0.0...v11.1.0

---

<details>
<summary>中文</summary>

## MAARS 11.1.0 — 安全加固、会话管理、Vue 3 迁移

纯系统护栏改进——零业务逻辑变更。包含安全审计修复、会话管理、前端框架迁移、CI 加固和文档重写。

### 安全加固

- **SSE 认证**：从 URL query param（`?token=`）迁移到 `Authorization` header，使用 `fetch` + `ReadableStream` 实现——防止 token 泄露到服务器日志、浏览器历史和监控链路
- **页面关闭**：`sendBeacon` 替换为 `fetch(..., { keepalive: true, headers })`，token 不再出现在 URL
- **移除 query param 兜底**：后端中间件不再接受 `?token=`，仅接受 `Authorization: Bearer`
- **启动告警**：未设置 `MAARS_API_KEY` 时打印黄色 WARNING

### 会话管理

- 会话历史 API：`GET /api/sessions`、`GET /api/sessions/{id}/state`、`DELETE /api/sessions/{id}`
- 从 DB 文件推导完整前端状态——零额外持久化
- 会话侧边栏：浏览、恢复、删除历史会话
- `beforeunload` 自动暂停 + 从 DB 产物断点续跑

### 前端：Vue 3 迁移

- 从原生 JS 迁移到 **Vue 3 + Pinia + Vite**
- 命令面板合入 ProgressBar 组件
- 新增会话侧边栏组件

### CI 与基础设施

- CI 新增前端构建验证（`npm ci && npm run build`）
- 按阶段配置模型：`MAARS_{STAGE}_PROVIDER` / `MAARS_{STAGE}_MODEL`
- 文件 DB：原子写入（`os.replace()`）+ 线程安全锁
- 测试覆盖扩展到 **120 个**

### 清理

- 删除死代码 `backend/pipeline/write.py`（308 行，零引用）
- 删除 research 中 `best_score.json` 向后兼容 fallback
- 删除未使用的 outline/section DB 方法和前端 phase 标签
- README、README_CN、`docs/CN/architecture.md` 完全重写

</details>

---

## v11.1.1: Skills Directory, Config Cleanup, Node 24 Baseline `v11.1.1`

*发布于 2026-03-31*

System-level cleanup release with no product workflow changes. This update consolidates configuration docs into `.env.example`, introduces a repository-local `skills/` directory for MAARS-specific workflows, aligns CI and local frontend development on Node 24+, and clears CI lint regressions.

### Changed

- `.env.example` is now the single source of truth for all supported `MAARS_` settings
- README and README_CN now point configuration guidance to `.env.example` instead of maintaining duplicated config tables
- Roadmap completed items were archived out of `docs/ROADMAP.md` into `docs/archive/roadmap-completed.md`
- MAARS-specific project workflows now live under the new `skills/` directory, with a repository-local release skill and bilingual release note templates
- Frontend development now targets Node 24+ locally, while CI frontend builds run on Node 24

### Fixed

- Removed unused imports that were failing `ruff` in CI
- GitHub Actions now opt JavaScript actions into Node 24 to avoid the Node 20 deprecation path

### Validation

- `pytest tests/ -q`
- `cd frontend && npm run build`

### Notes

- No business logic or pipeline behavior changed in this release
- Root skill documentation remains available via `SKILL.md`, while detailed project workflows live under `skills/`

**Full Changelog**: https://github.com/dozybot001/MAARS/compare/v11.1.0...v11.1.1

---

<details>
<summary>中文</summary>

这是一次系统层的收口发布，没有引入新的产品工作流变化。本次更新把配置说明统一收敛到 `.env.example`，新增仓库内的 `skills/` 目录用于沉淀 MAARS 专属流程，前端开发与 CI 一起对齐到 Node 24 主线，并顺手清掉了导致 CI 失败的 lint 问题。

### Changed

- `.env.example` 现在作为全部 `MAARS_` 配置项的唯一说明来源
- README 和 README_CN 不再维护重复的配置表，统一改为指向 `.env.example`
- `docs/ROADMAP.md` 中已完成事项迁移到 `docs/archive/roadmap-completed.md`
- 新增仓库级 `skills/` 目录，收纳 MAARS 专属流程；其中包含项目自己的发版 skill 和双语 release notes 模板
- 前端本地开发环境改为 Node 24+，CI 中的前端构建也同步跑在 Node 24 上

### Fixed

- 删除导致 CI 中 `ruff` 失败的未使用 import
- GitHub Actions 现在显式切到 Node 24 运行 JavaScript actions，避开 Node 20 退役路径

### Validation

- `pytest tests/ -q`
- `cd frontend && npm run build`

### Notes

- 本次发布不包含业务逻辑或 pipeline 行为变更
- 根目录 `SKILL.md` 继续作为入口索引，详细项目流程统一沉淀在 `skills/` 下

</details>

---

## v12.0.0: SSE Architecture Rewrite — DB-Driven State, Simplified Pipeline `v12.0.0`

*发布于 2026-04-01*

## MAARS 12.0.0 — SSE Architecture Rewrite

Rolled back to v11.0.0 and rebuilt: simplified the entire event system, concurrency model, and frontend rendering. Focus on **running the full pipeline reliably** before adding engineering infrastructure.

Net result: **-961 lines** (1937 added, 2898 removed across 30 files).

### Unified SSE Architecture

The entire event system is now one format: `{stage, phase?, chunk?, status?, task_id?}`

- **Has `chunk`** = phase in progress → left panel renders streaming text
- **No `chunk`** = done signal → right panel fetches DB and renders structured data
- **`status` field** = task intermediate state (running / verifying / retrying)

One `_send()` method replaces 10+ event types (`state`, `phase`, `chunk`, `tree`, `task_state`, `document`, `score`, `tokens`, `exec_tree`, `error`).

### DB as Single Source of Truth

All state persists to files — survives page refresh:

- `log.jsonl` — streaming chunks (append-only, replaces ephemeral SSE)
- `execution_log.jsonl` — Docker code execution history (was in-memory)
- `plan_list.json` — tasks with `status` + `batch` fields
- `plan_tree.json` — decomposition tree, updated after each judge
- `meta.json` — phase, score, tokens

`events.jsonl` removed (redundant with the above).

New read-only API: `/api/session/log`, `/api/session/plan/tree`, `/api/session/plan/list`, `/api/session/meta`, `/api/session/documents/{name}`.

### Frontend: Data-Driven Rendering

Three listeners, one event:

- **pipeline-ui**: only reacts to first-appearance of new stage/phase — end previous, light up current. No API polling during run.
- **log-viewer**: sections created on demand by first chunk (not by state events). No event ordering dependency.
- **process-viewer**: done signals trigger DB fetch → render. Container captured before async fetch to prevent race conditions.

### Concurrency Simplified

Single `MAARS_API_CONCURRENCY` controls everything. Removed `MAARS_DOCKER_SANDBOX_CONCURRENCY` — the API semaphore in `_stream_llm` naturally limits both decompose judges and task execution. Labels emitted inside semaphore (only the active call shows its label).

### Pipeline Simplification

- `_execute()` split into `_prepare()` + `_run_iterations()` with `_check_stop()` at every phase boundary
- `AgnoClient` wrapper removed — `_stream_llm` calls Agno Agent directly
- `Stage` + `AgentStage` merged into single `Stage` class
- `**kwargs` removed from all constructors (prevents silent argument swallowing)
- `_AUTO` prompt constant unified (was duplicated across 2 files + 2 inline copies)
- `save_task_output` agent tool removed (conflicting write path)
- `_find_running_stage` + `_find_paused_stage` merged into `_find_stage(state)`
- `_stream_llm` + `_stream_llm_inner` merged into single method
- `get_plan_list()` returns `list[dict]` (was raw JSON string)
- `get_plan_tree()` returns `dict` (was raw JSON string)
- `max_iterations` removed from Team constructor (only affects tasks mode, not coordinate)
- `threading.Lock` on `_active_containers` (thread-safety fix)
- Topological cycle warning (was silent fallback)
- `_cancel_pipeline` exception narrowed (was `except Exception: pass`)
- Token counting deduplicated (TeamRunCompleted only, was double-counted)
- Execution log persisted to file (was in-memory, lost on refresh)

### Start Script

Checklist-style startup with ASCII logo, grouped health checks, temp log file (deleted on clean exit).

**Full Changelog**: https://github.com/dozybot001/MAARS/compare/v11.0.0...v12.0.0

---

<details>
<summary>中文</summary>

## MAARS 12.0.0 — SSE 架构重写

从 v11.0.0 回退重建：简化整个事件系统、并发模型和前端渲染。优先**跑通跑稳完整流水线**，暂不搭建工程化基础设施。

净减少 **961 行**（30 个文件，新增 1937 行，删除 2898 行）。

### 统一 SSE 架构

整个事件系统统一为一种格式：`{stage, phase?, chunk?, status?, task_id?}`

- **有 `chunk`** = 阶段进行中 → 左侧面板渲染流式文本
- **无 `chunk`** = 结束信号 → 右侧面板从 DB 取数据渲染结构化内容
- **`status` 字段** = 任务中间状态（running / verifying / retrying）

一个 `_send()` 方法替代了 10+ 种事件类型。

### DB 作为唯一数据源

所有状态持久化到文件，刷新不丢失：

- `log.jsonl` — 流式 chunk（追加写入，替代瞬态 SSE）
- `execution_log.jsonl` — Docker 代码执行记录（原为内存列表）
- `plan_list.json` — 任务列表，含 `status` + `batch` 字段
- `plan_tree.json` — 分解树，每个 judge 完成后更新
- `meta.json` — 阶段、分数、token 统计

`events.jsonl` 已移除（上述文件覆盖其功能）。

新增只读 API：`/api/session/log`, `/api/session/plan/tree`, `/api/session/plan/list`, `/api/session/meta`, `/api/session/documents/{name}`。

### 前端：数据驱动渲染

三个监听器，同一个事件：

- **pipeline-ui**：仅在首次出现新 stage/phase 时触发——结束上一阶段，点亮当前阶段。运行期间不调 API。
- **log-viewer**：section 由第一个 chunk 按需创建，不依赖事件顺序。
- **process-viewer**：结束信号触发 DB 读取 → 渲染。异步 fetch 前捕获容器，防止竞态条件。

### 并发简化

单一 `MAARS_API_CONCURRENCY` 控制所有并发。移除 `MAARS_DOCKER_SANDBOX_CONCURRENCY`——`_stream_llm` 中的 API 信号量自然限制分解 judge 和任务执行的并发。标签在 semaphore 内部发送（只有正在执行的调用显示标签）。

### 流水线简化

- `_execute()` 拆分为 `_prepare()` + `_run_iterations()`，每个阶段边界有 `_check_stop()`
- 移除 `AgnoClient` 包装——`_stream_llm` 直接调用 Agno Agent
- `Stage` + `AgentStage` 合并为单一 `Stage` 类
- 构造器移除 `**kwargs`（防止静默吞参数）
- `_AUTO` 提示常量统一（原在 2 个文件 + 2 处内联副本中重复）
- 移除 `save_task_output` agent 工具（与 pipeline 写入路径冲突）
- 合并/简化：`_find_stage`、`_stream_llm`、`get_plan_list`、`get_plan_tree`
- Team 构造器移除 `max_iterations`（仅对 tasks 模式有效，coordinate 模式无效）
- `_active_containers` 加 `threading.Lock`（线程安全修复）
- 拓扑排序环检测加 warning（原为静默回退）
- `_cancel_pipeline` 异常处理缩窄（原为 `except Exception: pass`）
- token 计数去重（仅在 TeamRunCompleted 计算，原双重计算）
- 执行日志持久化到文件（原为内存，刷新丢失）

### 启动脚本

Checklist 风格启动，含 ASCII logo、分组健康检查、临时日志文件（正常退出时删除）。

**完整变更日志**: https://github.com/dozybot001/MAARS/compare/v11.0.0...v12.0.0

</details>

---

## v13.0.0: Pipeline Prompt Audit & Architecture Overhaul `v13.0.0`

*发布于 2026-04-03*

## MAARS 13.0.0 — Pipeline Prompt Audit & Architecture Overhaul

Full audit and restructuring of the Research pipeline: every stage's input/output reviewed, prompt system rebuilt for bilingual support, execution architecture simplified, frontend rewritten as state dashboard.

Net result: **+861 lines** (2096 added, 1235 removed across 26 files).

### Bilingual Prompt System

- `prompts.py` becomes a thin dispatcher selecting `prompts_zh.py` or `prompts_en.py` based on `MAARS_OUTPUT_LANGUAGE`
- Instructions and output language unified per file — no more English instructions with Chinese output directives
- Zero hardcoded constraints in prompts — all limits come from dynamic capability profile

### Capability Grounding

- `_build_capability_profile()`: deterministic profile from config (sandbox timeout/memory/CPU/network/tools)
- `_describe_dataset()`: scans dataset_dir for file names and sizes
- Calibrate, Strategy, Execute, Evaluate all receive the profile — LLM decisions grounded in real constraints
- Decompose stopping rules defer to Calibrate's definition instead of hardcoded "one file = atomic"

### Decompose Engine

- `root_id` parameter: `decompose()` works on any tree node, not just root "0"
- Redecompose: `decompose(root_id=task_id)` — zero ID remapping, deleted `_renumber_subtree` and `_redecompose_parent`
- Sibling context: each node sees its siblings during decomposition, preventing duplicate tasks
- Tool access: decompose agent can search web and read task outputs before judging

### Execute & Verify

- API semaphore wraps entire execute→verify→retry cycle per task (atomic, not per LLM call)
- `SUMMARY:` line written by execute agent — creator knows best; verify only checks artifacts exist
- Dependency summaries injected into execute prompt, reducing `read_task_output` calls
- Verify fallback changed from `pass:true` to `pass:false`

### Evaluate → Strategy Feedback Loop

- Replan removed entirely — replaced by Evaluate → Strategy Update → Decompose cycle
- Evaluate controls iteration via `strategy_update` field (present = continue, absent = stop)
- `max_iterations` enforced via `is_final` flag in evaluate prompt, not external for-loop
- Prior evaluations passed with "already attempted" label to avoid repeating suggestions

### Unified Loop

- Single `while True` loop: Strategy → Decompose → Execute → Evaluate
- `evaluation=None` distinguishes first pass — no `_prepare()` / `_run_iterations()` split
- Round labels consistent across all stages, owned by loop body only
- `plan_tree.json` = single source of truth; `plan_list.json` = derived cache
- Versioned documents: `strategy/round_N.md`, `evaluations/round_N.json` + `round_N.md`

### Frontend Rewrite

- Right panel rewritten as state dashboard: fixed containers for docs, score, tree, exec list
- Document cards: scan backend for versions, click to view full markdown (rendered via marked.js)
- Task click: shows full `tasks/{id}.md` output, not one-line summary
- Score: incremental append per round
- Status event buffering for race condition between exec list render and first task running
- Timer pause/resume on pipeline stop; NoCacheStaticMiddleware prevents stale JS

### Bug Fixes

- Task `_current_task_id` race condition under asyncio.gather — moved inside semaphore
- Missing `improved` flag in `update_meta` — score styling was always "declined"
- Duplicate level-2 labels from internal methods removed
- Round 2 decompose tree was overwriting round 1 — fixed with `root_id` + append
- `auto_release_port` kills any process on port, TERM then KILL
- `PHASE_LABELS` reference crashed done signal handler after deletion
- `clear_plan` now cleans both strategy/ and evaluations/ directories

**Full Changelog**: https://github.com/dozybot001/MAARS/compare/v12.0.0...v13.0.0

---

<details>
<summary>中文</summary>

## MAARS 13.0.0 — 流水线 Prompt 审查与架构重构

对研究流水线进行全面审查和重构：逐阶段审查输入输出、重建双语 Prompt 体系、简化执行架构、前端重写为状态仪表盘。

净变化：**+861 行**（26 个文件，新增 2096，删除 1235）。

### 双语 Prompt 体系

- `prompts.py` 变为薄分发层，根据 `MAARS_OUTPUT_LANGUAGE` 选择 `prompts_zh.py` 或 `prompts_en.py`
- 每个语言文件的指令语言与输出语言一致，消除混搭
- Prompt 模板中零硬编码约束——所有限制来自动态能力画像

### 能力接地

- `_build_capability_profile()`：从 config 确定性生成能力画像（沙箱超时/内存/CPU/网络/工具）
- `_describe_dataset()`：扫描 dataset_dir 获取文件名和大小
- Calibrate、Strategy、Execute、Evaluate 都接收能力画像，LLM 决策基于真实约束
- Decompose 停止规则指向 Calibrate 的动态定义，而非硬编码"一个文件=原子"

### 分解引擎

- `root_id` 参数：`decompose()` 可在任意树节点上工作
- 重分解：`decompose(root_id=task_id)`——零 ID 重映射，删除 `_renumber_subtree` 和 `_redecompose_parent`
- 兄弟上下文：分解时看到同级任务，避免重复
- 工具访问：分解 agent 可搜索网页、阅读已完成任务产出

### 执行与验证

- API semaphore 包裹整个 execute→verify→retry 周期（原子化）
- Execute agent 写 `SUMMARY:` 行；Verify 只检查产出文件是否存在
- 依赖摘要注入 execute prompt，减少 `read_task_output` 调用
- Verify fallback 从 `pass:true` 改为 `pass:false`

### 评估→策略反馈环

- 废弃 Replan，改为 Evaluate → Strategy Update → Decompose 循环
- Evaluate 通过 `strategy_update` 字段控制迭代（有=继续，无=停止）
- `max_iterations` 通过 `is_final` 标志在 prompt 中实施
- 历史评估标注"已尝试"传入，避免重复建议

### 统一循环

- 单一 `while True` 循环：Strategy → Decompose → Execute → Evaluate
- `evaluation=None` 区分首轮，消除 `_prepare()` / `_run_iterations()` 分裂
- 标签统一由循环体发出，内部方法不发标签
- `plan_tree.json` 为唯一真值，`plan_list.json` 为派生缓存
- 版本化文档：`strategy/round_N.md`、`evaluations/round_N.json` + `round_N.md`

### 前端重写

- 右面板重写为状态仪表盘：文档卡片、分数、分解树、执行列表各自独立更新
- 文档卡片：扫描后端获取版本列表，点击弹窗 markdown 渲染（marked.js）
- 任务点击：显示完整 `tasks/{id}.md` 产出
- 分数：每轮追加
- 状态事件缓冲：解决执行列表渲染与首个任务 running 事件的竞态
- 计时器暂停/恢复；NoCacheStaticMiddleware 防止 JS 缓存

### 问题修复

- `_current_task_id` 在 asyncio.gather 下竞态——移入 semaphore 内
- `update_meta` 缺失 `improved` 标志——分数样式始终显示"下降"
- 内部方法重复发送 level-2 标签
- Round 2 分解树覆盖 round 1——通过 `root_id` + 追加修复
- `auto_release_port` 强杀端口进程（TERM 后 KILL）
- `PHASE_LABELS` 删除后残留引用导致崩溃
- `clear_plan` 统一清理 strategy/ 和 evaluations/

**完整变更日志**: https://github.com/dozybot001/MAARS/compare/v12.0.0...v13.0.0

</details>

---

## MAARS v13.0.1 — Docs consolidation & dataset path unification `v13.0.1`

*发布于 2026-04-04*

## MAARS v13.0.1 — Docs consolidation & dataset path unification

Merged three separate docs into one architecture document, simplified both READMEs down to essentials, and unified the dataset directory so Kaggle mode uses the same configured path.

Net result: **-652 lines** (349 added, 1001 removed across 12 files).

### Documentation

- Merged `research-workflow.md` and `SSE_REFACTOR.md` into `docs/CN/architecture.md`
- Replaced scattered ASCII/mermaid diagrams with a single unified pipeline mermaid (TB layout)
- Simplified READMEs to features, quick start, and full config table — detailed design defers to architecture doc
- Added release note template (`docs/RELEASE_NOTE_TEMPLATE.md`)

### Dataset Path

- Kaggle mode now downloads directly into `MAARS_DATASET_DIR` instead of a hardcoded subdirectory
- Removed fallback defaults — single source of truth via `.env`
- `.env.example` sets `MAARS_DATASET_DIR=data/` as default

**Full Changelog**: https://github.com/dozybot001/MAARS/compare/v13.0.0...v13.0.1

---

<details>
<summary>中文</summary>

## MAARS v13.0.1 — 文档合并与数据集路径统一

将三份独立文档合并为一份架构文档，精简两个 README 至核心内容，统一数据集目录使 Kaggle 模式复用同一配置路径。

净变化：**-652 行**（12 个文件，新增 349，删除 1001）。

### 文档

- 将 `research-workflow.md` 和 `SSE_REFACTOR.md` 合入 `docs/CN/architecture.md`
- 用一张统一的 mermaid 流水线图（竖版）替代分散的 ASCII/mermaid 图
- README 精简为功能、快速开始、完整配置表——详细设计指向架构文档
- 新增 release note 模板（`docs/RELEASE_NOTE_TEMPLATE.md`）

### 数据集路径

- Kaggle 模式直接下载到 `MAARS_DATASET_DIR`，不再创建硬编码子目录
- 移除 fallback 默认值——`.env` 为唯一配置源
- `.env.example` 默认 `MAARS_DATASET_DIR=data/`

**完整变更日志**: https://github.com/dozybot001/MAARS/compare/v13.0.0...v13.0.1

</details>

---

## MAARS v13.0.2 — Research pipeline bug fixes `v13.0.2`

*发布于 2026-04-04*

## MAARS v13.0.2 — Research pipeline bug fixes

Three bugs fixed in the Research stage after a full code review of the execution pipeline.

Net result: **+5 lines** (11 added, 6 removed across 3 files).

### Bug Fixes

- **Score tracking now works**: `promote_best_score()` is called after each task completes, so Evaluate can see score progression across rounds
- **Decompose guard**: LLM returning `is_atomic: false` with empty or invalid subtasks no longer silently drops the task — falls back to atomic
- **Dedup status update**: removed redundant `update_task_status("failed")` in `_run_task_cycle` (already handled by caller)

**Full Changelog**: https://github.com/dozybot001/MAARS/compare/v13.0.1...v13.0.2

---

<details>
<summary>中文</summary>

## MAARS v13.0.2 — Research 流水线 bug 修复

对 Research 阶段执行流水线完整代码审查后修复三个 bug。

净变化：**+5 行**（3 个文件，新增 11，删除 6）。

### 问题修复

- **分数追踪修复**：每个任务完成后调用 `promote_best_score()`，Evaluate 阶段现在能看到跨轮次的分数变化
- **分解防御**：LLM 返回 `is_atomic: false` 但 subtasks 为空或无效时，不再静默丢弃任务，回退为原子任务
- **去重状态更新**：移除 `_run_task_cycle` 中重复的 `update_task_status("failed")`（由调用方统一处理）

**完整变更日志**: https://github.com/dozybot001/MAARS/compare/v13.0.1...v13.0.2

</details>

---

## MAARS v13.1.0 — Team agent tool upgrades `v13.1.0`

*发布于 2026-04-04*

## MAARS v13.1.0 — Team agent tool upgrades

Equipped Refine and Write team agents with proper tools so they can independently verify claims instead of relying on text alone.

Net result: **+23 lines** (38 added, 15 removed across 6 files).

### Refine Team

- **Critic** now has search tools (DuckDuckGo, arXiv, Wikipedia) to independently verify literature claims in proposals

### Write Team

- **Reviewer** now has `db_tools` + `list_artifacts` to cross-check paper content against original task outputs, plan tree, and artifact files
- **Writer** artifact image paths fixed: prompt now references `artifacts/<task_id>/filename.png` using `list_artifacts` output instead of incorrect flat paths
- `list_artifacts` upgraded to recursive listing when called without task context (Write stage), returning relative paths for all session artifacts

### Factory

- `WriteStage` accepts explicit `reviewer_tools` parameter — clean separation from writer tools

**Full Changelog**: https://github.com/dozybot001/MAARS/compare/v13.0.2...v13.1.0

---

<details>
<summary>中文</summary>

## MAARS v13.1.0 — Team agent 工具升级

为 Refine 和 Write 团队的 agent 配备了恰当的工具，使其能够独立验证内容而非仅依赖文本。

净变化：**+23 行**（6 个文件，新增 38，删除 15）。

### Refine 团队

- **Critic** 获得搜索工具（DuckDuckGo、arXiv、Wikipedia），可独立查证提案中的文献论断

### Write 团队

- **Reviewer** 获得 `db_tools` + `list_artifacts`，可对照原始任务输出、计划树和 artifact 文件交叉验证论文内容
- **Writer** artifact 图片路径修正：prompt 改为使用 `list_artifacts` 返回的 `artifacts/<task_id>/filename.png` 格式
- `list_artifacts` 在无任务上下文时（Write 阶段）支持递归列出全部 session 文件及相对路径

### Factory

- `WriteStage` 接受显式 `reviewer_tools` 参数，与 writer 工具清晰分离

**完整变更日志**: https://github.com/dozybot001/MAARS/compare/v13.0.2...v13.1.0

</details>

---

## MAARS v13.2.0 — Configurable team delegations & UI fixes `v13.2.0`

*发布于 2026-04-04*

## MAARS v13.2.0 — Configurable Team Delegations & UI Fixes

Refine/Write stages now support configurable iteration rounds instead of hardcoded 3 delegations. Fixed Agno 2.5.11 compatibility and several UI issues.

Net result: **+29 lines** (71 added, 42 removed across 13 files).

### Team Delegations

- Add `MAARS_TEAM_MAX_DELEGATIONS` env config for Refine/Write round limits
- Remove hardcoded "exactly 3 delegations" from prompts, allow iterative refinement until Critic/Reviewer is satisfied

### Compatibility

- Fix `team.arun()` for Agno 2.5.11 (returns async generator, not awaitable)
- Remove unused `kaggle_competition_id` from config
- Remove hardcoded defaults from config.py (all values from .env)

### Bug Fixes

- Fix tool call_id collisions: each tool call gets its own fold in log viewer
- Fix modal word-wrap: change `<pre>` to `<div>`, add pre-wrap for code blocks

**Full Changelog**: https://github.com/dozybot001/MAARS/compare/v13.1.0...v13.2.0

---

<details>
<summary>中文</summary>

## MAARS v13.2.0 — 可配置团队委派轮次与 UI 修复

Refine/Write 阶段支持可配置的迭代轮次，替代硬编码的 3 次委派。修复 Agno 2.5.11 兼容性及多个 UI 问题。

净变化：**+29 行**（13 个文件，新增 71，删除 42）。

### 团队委派

- 新增 `MAARS_TEAM_MAX_DELEGATIONS` 环境变量，控制 Refine/Write 最大轮次
- 移除 prompt 中"恰好 3 次委派"的硬编码限制，允许迭代直到 Critic/Reviewer 满意

### 兼容性

- 修复 Agno 2.5.11 的 `team.arun()` 接口变更（异步生成器而非可等待对象）
- 移除无用的 `kaggle_competition_id` 配置项
- 移除 config.py 中的硬编码默认值（全部从 .env 读取）

### 问题修复

- 修复工具 call_id 冲突：每个工具调用使用唯一 ID，独立折叠
- 修复弹窗自动换行：`<pre>` 改为 `<div>`，代码块添加 pre-wrap

**完整变更日志**: https://github.com/dozybot001/MAARS/compare/v13.1.0...v13.2.0

</details>

---

## MAARS v13.3.0 — Custom orchestration loop & Gemini Search `v13.3.0`

*发布于 2026-04-04*

## MAARS v13.3.0 — Custom Orchestration Loop & Gemini Search

Replace Agno Team coordinate mode with a self-orchestrated primary/reviewer loop using ProposalState for constant-size context management. Switch web search from DuckDuckGo to Gemini native Google Search.

Net result: **+152 lines** (603 added, 451 removed across 18 files).

### Architecture

- Replace Agno Team coordinate mode with custom orchestration loop (ProposalState)
- Constant-size context per iteration: latest proposal + unresolved issues only, no linear growth
- Structured feedback: Critic/Reviewer outputs JSON `{pass, issues, resolved}`
- Delete Leader agent — deterministic routing saves tokens and latency

### Search

- Enable Gemini native Google Search (`search=True`), remove DuckDuckGo (was unreliable, caused hangs)
- Keep ArxivTools and WikipediaTools for academic search

### Persistence

- Save proposals (`proposals/round_N.md`) and critiques (`critiques/round_N.md` + `.json`) per round
- Done signals trigger right panel document card updates

### Frontend

- Reorganize right panel by pipeline stage: Refine / Research / Decompose / Tasks / Write
- Split Research documents into Calibration / Strategies / Evaluations rows
- Add SSE connection indicator (green/red dot)
- Fixed-height doc card rows with horizontal scroll, newest first

### Bug Fixes

- Check Docker before entering Research stage (fail fast, not after calibrate)
- Expose issue IDs in format_issues() for correct resolved tracking
- Use path type for document route to support subdirectory names
- Fix evaluation PHASE_DOCS mapping (was missing 's')

**Full Changelog**: https://github.com/dozybot001/MAARS/compare/v13.2.0...v13.3.0

---

<details>
<summary>中文</summary>

## MAARS v13.3.0 — 自编排循环与 Gemini 搜索

用自编排的 primary/reviewer 循环替代 Agno Team coordinate 模式，通过 ProposalState 实现恒定大小的上下文管理。网页搜索从 DuckDuckGo 切换为 Gemini 原生 Google Search。

净变化：**+152 行**（18 个文件，新增 603，删除 451）。

### 架构

- 用自编排循环（ProposalState）替代 Agno Team coordinate 模式
- 每轮上下文大小恒定：仅包含最新提案 + 未解决问题，不随轮次增长
- 结构化反馈：Critic/Reviewer 输出 JSON `{pass, issues, resolved}`
- 删除 Leader agent — 确定性路由，节省 token 和延迟

### 搜索

- 启用 Gemini 原生 Google Search（`search=True`），移除 DuckDuckGo（不稳定，常卡死）
- 保留 ArxivTools 和 WikipediaTools 用于学术搜索

### 持久化

- 每轮保存提案（`proposals/round_N.md`）和评审（`critiques/round_N.md` + `.json`）
- Done signal 触发右侧面板文档卡片更新

### 前端

- 右侧面板按流水线阶段重组：Refine / Research / Decompose / Tasks / Write
- Research 文档拆分为 Calibration / Strategies / Evaluations 三行
- 新增 SSE 连接指示灯（绿色/红色圆点）
- 文档卡片行固定高度，横向滚动，最新在最左

### 问题修复

- Research 阶段入口即检查 Docker（不再等 calibrate 完成后才报错）
- format_issues() 暴露 issue ID，修复 resolved 字段追踪
- 文档路由使用 path 类型，支持子目录名
- 修复 evaluation PHASE_DOCS 映射（缺少 's'）

**完整变更日志**: https://github.com/dozybot001/MAARS/compare/v13.2.0...v13.3.0

</details>

---

## MAARS v13.4.0 — Write Stage Alignment & Cleanup `v13.4.0`

*发布于 2026-04-04*

## MAARS v13.4.0 — Write Stage Alignment & Cleanup

Write stage now uses the same TeamStage/IterationState pattern as Refine. Renamed core abstractions for clarity, cleaned up all dead code.

Net result: **+27 lines** (115 added, 88 removed across 12 files).

### Write Stage

- Write stage reuses TeamStage loop (Writer + Reviewer), fully symmetric with Refine
- Separate persistence directories: `drafts/` + `reviews/` (vs Refine's `proposals/` + `critiques/`)
- Separate SSE phases: `draft`/`review` (vs Refine's `proposal`/`critique`)
- Remove research tools (ArxivTools/WikipediaTools) from Writer — should use existing outputs only
- Writer prompt: summary-first workflow (list_tasks for summaries, then read_task_output selectively)
- Fix artifact path format in Writer prompt to match list_artifacts output

### Naming & Abstractions

- `ProposalState` -> `IterationState`, `proposal` -> `draft` — generic for both stages
- `"Proposal to Review"` -> `"Content to Review"` in reviewer prompt
- Configurable dir/phase names via class variables (`_primary_dir`, `_reviewer_dir`, `_primary_phase`, `_reviewer_phase`)
- Generalized persistence: `_save_round_md` / `_save_round_json` in TeamStage

### Cleanup

- Enhance `list_tasks` tool: return `{id, description, summary, status}` from plan_list.json
- Remove unused CORSMiddleware import
- Remove orphaned `.folded` CSS class
- Update architecture doc to v13.3.0 with complete storage structure

**Full Changelog**: https://github.com/dozybot001/MAARS/compare/v13.3.0...v13.4.0

---

<details>
<summary>中文</summary>

## MAARS v13.4.0 — Write 阶段对齐与清理

Write 阶段现在和 Refine 使用相同的 TeamStage/IterationState 模式。重命名核心抽象以提升清晰度，清理所有死代码。

净变化：**+27 行**（12 个文件，新增 115，删除 88）。

### Write 阶段

- Write 阶段复用 TeamStage 循环（Writer + Reviewer），与 Refine 完全对称
- 独立持久化目录：`drafts/` + `reviews/`（对比 Refine 的 `proposals/` + `critiques/`）
- 独立 SSE phase：`draft`/`review`（对比 Refine 的 `proposal`/`critique`）
- 从 Writer 工具中移除搜索工具（ArxivTools/WikipediaTools）——应仅使用已有研究产出
- Writer prompt：先看摘要再按需读详情
- 修正 artifact 路径格式以匹配 list_artifacts 实际输出

### 命名与抽象

- `ProposalState` -> `IterationState`，`proposal` -> `draft`——两个阶段通用
- 审阅 prompt 中 `"Proposal to Review"` -> `"Content to Review"`
- 通过类变量配置目录名/phase 名
- 通用化持久化方法：TeamStage 中的 `_save_round_md` / `_save_round_json`

### 清理

- 增强 `list_tasks` 工具：返回 `{id, description, summary, status}`
- 移除未使用的 CORSMiddleware 导入
- 移除孤立的 `.folded` CSS 类
- 更新架构文档至 v13.3.0，包含完整存储结构

**完整变更日志**: https://github.com/dozybot001/MAARS/compare/v13.3.0...v13.4.0

</details>

---

## MAARS v13.4.1 — Documentation Overhaul `v13.4.1`

*发布于 2026-04-04*

## MAARS v13.4.1 — Documentation Overhaul

Complete documentation rewrite: split architecture into focused docs, add EN translations, rewrite README for professional distribution.

Net result: **+717 lines** (1020 added, 303 removed across 8 files).

### Architecture Docs

- Split monolithic `architecture.md` into three focused documents:
  - **architecture.md** — system overview, SSE protocol, storage, code structure
  - **refine-write.md** — IterationState pattern, dual-agent loop, Refine/Write comparison
  - **research.md** — agentic workflow, parallel execution, key decisions
- Full EN/CN parity: `docs/EN/` mirrors `docs/CN/`

### README

- Rewrite README.md and README_CN.md for professional GitHub distribution
- Pipeline diagram, "How It Works" section, complete config table
- Output structure, documentation index, tech stack

**Full Changelog**: https://github.com/dozybot001/MAARS/compare/v13.4.0...v13.4.1

---

<details>
<summary>中文</summary>

## MAARS v13.4.1 — 文档全面改版

完整文档重写：架构文档拆分为专题文档，新增英文翻译，README 按专业分发标准重写。

净变化：**+717 行**（8 个文件，新增 1020，删除 303）。

### 架构文档

- 单体 `architecture.md` 拆分为三份专题文档：overview / refine-write / research
- 中英完全对称：`docs/EN/` 与 `docs/CN/` 镜像

### README

- 重写 README.md 和 README_CN.md
- 流水线图、工作原理、完整配置表、产出结构、文档索引、技术栈

**完整变更日志**: https://github.com/dozybot001/MAARS/compare/v13.4.0...v13.4.1

</details>

---

## MAARS v13.4.2 — Documentation Polish `v13.4.2`

*发布于 2026-04-04*

## MAARS v13.4.2 — Documentation Polish

Final documentation pass: mermaid diagrams, language switch links, unified Multi-Agent terminology.

### Changes

- Replace all ASCII diagrams in README with mermaid (pipeline + IterationState loop)
- Add language switch links (中文 | English) to all docs and READMEs
- EN README links to EN docs, CN README links to CN docs
- Unify terminology: all stages are "Multi-Agent", remove "agentic workflow" and "DAG" sub-labels

**Full Changelog**: https://github.com/dozybot001/MAARS/compare/v13.4.1...v13.4.2

---

<details>
<summary>中文</summary>

## MAARS v13.4.2 — 文档打磨

最终文档整理：mermaid 图、双语切换链接、统一 Multi-Agent 术语。

### 变更

- README 中所有 ASCII 图替换为 mermaid（流水线 + IterationState 循环）
- 所有文档和 README 添加语言切换链接（中文 | English）
- 英文 README 链接英文文档，中文 README 链接中文文档
- 统一术语：所有阶段均为"Multi-Agent"，移除"agentic workflow"和"DAG"子标签

**完整变更日志**: https://github.com/dozybot001/MAARS/compare/v13.4.1...v13.4.2

</details>

---

## MAARS v13.4.3 — Terminology Unified to Multi-Agent `v13.4.3`

*发布于 2026-04-04*

## MAARS v13.4.3 — Terminology Unified to Multi-Agent

Unify project terminology: all stages are Multi-Agent, no sub-labels. Slim down README.

### Changes

- Remove "agentic workflow" and "DAG" labels from all docs and README
- Remove redundant "How It Works" section from README (pipeline diagram already covers it)
- Replace last ASCII diagram with mermaid
- Remove showcase directory (old format, no production cases yet)

**Full Changelog**: https://github.com/dozybot001/MAARS/compare/v13.4.2...v13.4.3

---

<details>
<summary>中文</summary>

## MAARS v13.4.3 — 术语统一为 Multi-Agent

统一项目术语：所有阶段均为 Multi-Agent，不加子标签。精简 README。

### 变更

- 移除所有文档和 README 中的"agentic workflow"和"DAG"标签
- 移除 README 中冗余的"工作原理"章节（流水线图已覆盖）
- 最后一个 ASCII 图替换为 mermaid
- 移除 showcase 目录（旧格式，暂无生产案例）

**完整变更日志**: https://github.com/dozybot001/MAARS/compare/v13.4.2...v13.4.3

</details>

---

## MAARS 13.4.4 — Checkpoint-Based Resume `v13.4.4`

*发布于 2026-04-04*

All pipeline stages now resume from disk state instead of restarting from scratch.

Net result: **+39 lines** (90 added, 51 removed across 3 files).

### Pause / Resume Overhaul

- **Refine & Write**: each primary/reviewer round checks disk before calling LLM — completed rounds are skipped, issues replayed from all saved critique JSONs
- **Research**: eliminated in-memory evaluation flag; strategy, decompose, and evaluate phases now branch on disk state and iteration count
- Added `get_strategy_for(iteration)` and `get_evaluation(iteration)` for targeted round lookups

### Bug Fixes

- Fixed resume incorrectly using stale strategy when iteration > 0 (was loading latest instead of updating from previous evaluation)

**Full Changelog**: https://github.com/dozybot001/MAARS/compare/v13.4.3...v13.4.4

---

<details>
<summary>中文</summary>

## MAARS 13.4.4 — 断点续传

所有流水线阶段现在从磁盘状态恢复，而不是从头重跑。

净变化：**+39 行**（3 个文件，新增 90，删除 51）。

### 暂停 / 恢复重构

- **Refine & Write**：每轮 primary/reviewer 先查磁盘，已完成的轮次直接跳过，issues 从所有已保存的 critique JSON 按序 replay
- **Research**：消除内存 evaluation 标志，strategy、decompose、evaluate 各阶段改为基于磁盘状态和 iteration 计数决定分支
- 新增 `get_strategy_for(iteration)` 和 `get_evaluation(iteration)` 按轮次精确读取

### 问题修复

- 修复 resume 时 iteration > 0 场景下错误复用旧 strategy（原逻辑加载最新版本而非基于上轮 evaluation 更新）

**完整变更日志**: https://github.com/dozybot001/MAARS/compare/v13.4.3...v13.4.4

</details>

---

## MAARS 13.4.5 — UI Refresh & Startup Improvements `v13.4.5`

*发布于 2026-04-04*

Replaced the hidden Cmd+K command palette with an always-visible top input bar. Startup script now verifies the Google API key before launching.

Net result: **-13 lines** (111 added, 124 removed across 17 files).

### UI: Input & Controls

- Top input bar always visible — type and press Enter to start, no hidden shortcuts needed
- Pause / Resume buttons moved to the right side of the pipeline progress bar
- Removed Cmd+K overlay and Start button
- Full viewport layout: input bar + progress bar + workspace fill the screen, panels scroll internally

### Startup

- `start.sh` clears terminal before displaying banner
- Google API key verified on startup with a minimal `generateContent` request — catches invalid keys or model names before the first real LLM call

### Docs

- Added terminal and UI screenshots to README (EN + CN)
- Unified Multi-Agent terminology across all active docs — removed "dual-agent loop", "single-agent workflow"
- Updated Refine/Write persistence row: all stages now support checkpoint/resume
- `.claude/` removed from tracking and added to `.gitignore`

**Full Changelog**: https://github.com/dozybot001/MAARS/compare/v13.4.4...v13.4.5

---

<details>
<summary>中文</summary>

## MAARS 13.4.5 — UI 刷新与启动优化

用顶部常驻输入栏替代了隐藏的 Cmd+K 面板。启动脚本新增 Google API Key 验证。

净变化：**-13 行**（17 个文件，新增 111，删除 124）。

### UI：输入与控制

- 顶部输入栏常驻显示，输入后按 Enter 即可启动，无需记快捷键
- Pause / Resume 按钮移至流程图右侧
- 移除 Cmd+K 弹窗和 Start 按钮
- 全视口布局：输入栏 + 进度条 + 工作区填满屏幕，面板内部自行滚动

### 启动

- `start.sh` 启动前清屏
- 启动时验证 Google API Key，发送最小 `generateContent` 请求，提前发现无效 key 或模型名

### 文档

- README（中英文）添加终端启动截图和 UI 截图
- 统一 Multi-Agent 术语，移除 "dual-agent loop"、"single-agent workflow" 等表述
- 更新 Refine/Write 持久化说明：所有阶段均支持 checkpoint/resume
- `.claude/` 移出版本跟踪，加入 `.gitignore`

**完整变更日志**: https://github.com/dozybot001/MAARS/compare/v13.4.4...v13.4.5

</details>

---

## MAARS 13.4.6 — End of the Self-Orchestrated Era `v13.4.6`

*发布于 2026-04-11*

This is the **final release of MAARS's original architecture** — the hand-written `Stage` / `TeamStage` runtime paired with Agno agents. Development continues on the [`langgraph`](https://github.com/dozybot001/MAARS/tree/langgraph) branch, where the project is being rewritten from scratch on top of LangGraph.

Going forward, `main` is frozen as an archival snapshot. All new work happens on `langgraph`.

Net result: **+69 lines** (188 added, 119 removed across 9 files).

### Why the Rewrite?

The original runtime (`Stage`, `TeamStage`, `IterationState`) is essentially a hand-written mini state-graph framework. LangGraph's `StateGraph` + `Conditional Edge` + `Checkpointer` express the same idea natively, so the project switches to the upstream framework and retires the bespoke runtime. See the [`langgraph` branch README](https://github.com/dozybot001/MAARS/blob/langgraph/README.md) for the rewrite plan.

### Bug Fixes

- Input bar is now disabled immediately on Enter, preventing a race where two submissions could fire back-to-back

### Docs

- Fixed outdated project structure in `CONTRIBUTING.md`
- Aligned README output structure with architecture docs
- Expanded data storage tree to show full directory / file hierarchy
- Switched architecture docs to Unicode tree characters for better rendering
- Updated README instructions to "press Enter" instead of "click Start"
- Renamed `terminal.png` → `tui.png` and refreshed UI screenshots

**Full Changelog**: https://github.com/dozybot001/MAARS/compare/v13.4.5...v13.4.6

---

<details>
<summary>中文</summary>

## MAARS 13.4.6 — 自编排时代终章

本次是 MAARS **原始架构的最后一次发布**——手写 `Stage` / `TeamStage` runtime 搭配 Agno agents 的最终版本。项目后续开发迁往 [`langgraph`](https://github.com/dozybot001/MAARS/tree/langgraph) 分支，基于 LangGraph 从零重写。

从此以后，`main` 冻结为原架构的归档快照，所有新的工作都在 `langgraph` 分支进行。

净变化：**+69 行**（9 个文件，新增 188，删除 119）。

### 为什么重写？

原 runtime（`Stage`、`TeamStage`、`IterationState`）本质上是一个手写的 mini state-graph 框架。LangGraph 的 `StateGraph` + `Conditional Edge` + `Checkpointer` 原生表达同样的思想，因此项目切换到上游框架，退役自建 runtime。重写计划详见 [`langgraph` 分支 README](https://github.com/dozybot001/MAARS/blob/langgraph/README.md)。

### 问题修复

- 输入栏在 Enter 按下后立即禁用，修复了两次提交可能连发的竞态

### 文档

- 修复 `CONTRIBUTING.md` 中过时的项目结构说明
- 对齐 README 产物结构与架构文档
- 数据存储树展开到完整的目录/文件层级
- 架构文档改用 Unicode 树形字符，渲染更稳定
- README 指引改为"按 Enter"而非"点击 Start"
- 资源文件重命名 `terminal.png` → `tui.png`，刷新 UI 截图

**完整变更日志**: https://github.com/dozybot001/MAARS/compare/v13.4.5...v13.4.6

</details>

---

## MAARS 13.4.7 — GPU Acceleration `v13.4.7`

*发布于 2026-04-14*

## MAARS 13.4.7 — GPU Acceleration

Docker sandbox now supports NVIDIA GPU passthrough, enabling deep learning workloads (PyTorch training, etc.) to run on GPU instead of CPU-only.

Net result: **+83 lines** (92 added, 9 removed across 7 files).

### GPU Support

- New `MAARS_DOCKER_SANDBOX_GPU` config option — set to `true` to enable GPU passthrough
- Sandbox base image switched from `python:3.12-slim` to `nvidia/cuda:12.8.0-runtime-ubuntu24.04`
- PyTorch install changed from CPU-only to CUDA 12.8 (`cu128`)
- `docker_exec.py` passes `device_requests` to Docker when GPU is enabled
- `start.sh` auto-detects GPU availability on startup and reports status

### Documentation

- GPU setup guide added to both README.md and README_CN.md — covers NVIDIA Container Toolkit installation, verification, and `.env` configuration

**Full Changelog**: https://github.com/dozybot001/MAARS/compare/v13.4.6...v13.4.7

---

<details>
<summary>中文</summary>

## MAARS 13.4.7 — GPU 加速

Docker 沙箱现已支持 NVIDIA GPU 透传，深度学习任务（PyTorch 训练等）可使用 GPU 而非仅 CPU 运行。

净变化：**+83 行**（7 个文件，新增 92，删除 9）。

### GPU 支持

- 新增 `MAARS_DOCKER_SANDBOX_GPU` 配置项——设为 `true` 即可启用 GPU 透传
- 沙箱基础镜像从 `python:3.12-slim` 切换为 `nvidia/cuda:12.8.0-runtime-ubuntu24.04`
- PyTorch 从 CPU 版切换为 CUDA 12.8（`cu128`）版
- `docker_exec.py` 在 GPU 启用时向 Docker 传递 `device_requests`
- `start.sh` 启动时自动检测 GPU 可用性并报告状态

### 文档

- 中英文 README 均新增 GPU 配置指南——涵盖 NVIDIA Container Toolkit 安装、验证和 `.env` 配置

**完整变更日志**: https://github.com/dozybot001/MAARS/compare/v13.4.6...v13.4.7

</details>

---

## MAARS 13.5.0 - Windows Launcher & File Input `v13.5.0`

*发布于 2026-04-14*

## Summary

This release makes MAARS easier to start on Windows and more flexible at kickoff: you can now start a run from a UTF-8 text/Markdown file path, while the runtime surfaces hardware constraints more explicitly for GPU-aware research planning and reproduction.

## Changes

### Added

- Added file-path input resolution for `/api/pipeline/start`, including a sample brief in `showcase/example-idea.md` and regression tests.
- Added runtime GPU disclosure in research prompts and capability profiles, plus GPU-aware `docker-compose` output for reproduction bundles.

### Changed

- Hardened `start.sh` for Windows Git Bash / MSYS workflows with better shell detection, port auto-release, venv discovery, browser launch, persistent logging, and shutdown handling.
- Updated the UI placeholder and bilingual docs to mention Windows Git Bash usage and file-path input support.

### Fixed

- Fixed startup cases where Git Bash could exit early after launching the server or leave port cleanup to manual intervention.

## Validation

- `python -m pytest tests/ -q`
- Frontend ships as checked-in static assets in `frontend/`; this repository currently has no `npm run build` step.

**Full Changelog**: https://github.com/dozybot001/MAARS/compare/v13.4.7...v13.5.0

---

<details>
<summary>中文</summary>

## 摘要

这次发布主要让 MAARS 在 Windows 上更容易启动，也让研究入口更灵活：现在可以直接用 UTF-8 文本/Markdown 文件路径启动任务，同时研究与复现实验阶段会更明确地披露 CPU/GPU 能力约束。

## 变更内容

### Added

- `/api/pipeline/start` 新增文件路径输入解析，附带 `showcase/example-idea.md` 示例和回归测试。
- 在研究提示词与能力画像中新增运行时 GPU 信息披露；复现实验导出的 `docker-compose` 也会在启用 GPU 时带上 `gpus: all`。

### Changed

- 强化了面向 Windows Git Bash / MSYS 的 `start.sh`：改进 shell 检测、端口自动释放、虚拟环境发现、浏览器打开、持久日志和退出处理。
- 更新了前端占位文案以及中英文文档，明确 Windows 使用 Git Bash，并说明支持文件路径输入。

### Fixed

- 修复了 Git Bash 启动后可能提前退出、以及端口占用需要手动清理的情况。

## 验证

- `python -m pytest tests/ -q`
- 前端当前以仓库内静态资源形式交付，仓库中不存在 `npm run build` 步骤。

**完整变更日志**: https://github.com/dozybot001/MAARS/compare/v13.4.7...v13.5.0

</details>

---

## MAARS 13.6.0 - Pipeline Efficiency & Reliability Overhaul `v13.6.0`

*发布于 2026-04-14*

## Summary

Major pipeline efficiency and reliability overhaul across four audit rounds. Docker sandbox switches from disposable containers to a persistent session container, eliminating ~190s of redundant `pip install` per task. Task decomposition is relaxed to produce fewer, meatier tasks — reducing LLM call count by ~50%. Multiple critical logic bugs are fixed, including a state-machine flaw that allowed the Write stage to run on incomplete research data.

## Changes

### Added

- Persistent Docker sandbox: a single container is reused across all `code_execute` calls in a research session; installed packages and files survive between calls.
- SSE broadcast: multiple browser tabs now each receive the full event stream instead of splitting events.
- Concurrency safety: `current_task_id` uses `contextvars` for per-coroutine isolation; orchestrator state transitions are protected by `asyncio.Lock`.
- Atomic JSON writes (`temp + rename`) to prevent data corruption on crash.
- Chinese i18n for Write stage instructions and Team stage scaffolding text.

### Changed

- Decompose threshold relaxed from 2–3 to 5–8 `code_execute` calls per task, with explicit guidance to prefer fewer tasks.
- Calibrate and Execute prompts now describe the persistent container and list pre-installed packages (torch, scikit-learn, etc.).
- Strategy prompt generalized from competition-focused to research-focused language.
- Retry prompt changed from "redo the task" to "fix only the identified issues."
- Verify step made tool-less (no more `list_artifacts` call per verify), saving one LLM round-trip per task.
- `_stream_llm` timeout now dynamically computed as `docker_sandbox_timeout + 600s` instead of hardcoded 1800s.
- Non-root decompose judge calls stripped of search tools to reduce token waste.
- Default `MAARS_TEAM_MAX_DELEGATIONS` lowered from 10 to 5.

### Fixed

- **Critical:** `Stage.run` no longer overwrites `FAILED` with `COMPLETED` — the Write stage will not run on broken research data.
- **Critical:** `max_iterations` is now enforced with a hard break, preventing infinite strategy-update loops.
- **High:** Redecompose dependency rewiring is now persisted to `plan_list.json`, preventing corrupt DAG on resume.
- **High:** `parse_json_fenced` rejects non-dict JSON (e.g. `[...]`) instead of passing it to callers that assume `.get()`.
- **High:** Decompose judge respects `is_atomic: true` even when the LLM also returns subtasks.
- **Medium:** `CancelledError` in `Stage.run` now sets state to `IDLE` instead of leaving it stuck at `RUNNING`.
- **Medium:** `_load_checkpoint` filters orphan task outputs by `plan_list.json` IDs.
- **Medium:** `get_iteration` only counts valid (non-corrupt) evaluation files.
- **Low:** Frontend input box re-enables on start failure.

## Validation

- `python -m pytest tests/ -q` — 7 passed
- Frontend ships as checked-in static assets; no build step required.

**Full Changelog**: https://github.com/dozybot001/MAARS/compare/v13.5.0...v13.6.0

---

<details>
<summary>中文</summary>

## 摘要

经过四轮深度审计，对整个研究流水线进行了效率和可靠性的全面升级。Docker 沙箱从一次性容器切换为持久会话容器，消除了每个任务约 190 秒的重复 `pip install` 开销。任务分解粒度放宽，LLM 调用次数减少约 50%。修复了多个严重逻辑 Bug，包括一个允许 Write 阶段在研究数据不完整时仍然运行的状态机缺陷。

## 变更内容

### 新增

- 持久 Docker 沙箱：整个研究会话复用单一容器，已安装的包和生成的文件在 `code_execute` 调用间保留。
- SSE 广播：多个浏览器标签页现在各自收到完整的事件流，而非分裂事件。
- 并发安全：`current_task_id` 使用 `contextvars` 实现协程级隔离；orchestrator 状态转换由 `asyncio.Lock` 保护。
- 原子 JSON 写入（临时文件 + 重命名），防止崩溃时数据损坏。
- Write 阶段指令和 Team 阶段交互文本的中文国际化。

### 变更

- 分解阈值从 2-3 次放宽至 5-8 次 `code_execute`，明确引导减少碎片化任务。
- 校准和执行 Prompt 现在描述持久容器并列出预装包（torch、scikit-learn 等）。
- 策略 Prompt 从竞赛导向改为通用研究导向。
- 重试 Prompt 从"重做任务"改为"仅修复已识别的问题"。
- 验证步骤去掉工具调用，每个任务节省一次 LLM 往返。
- `_stream_llm` 超时从硬编码 1800 秒改为 `docker_sandbox_timeout + 600` 秒动态计算。
- 非根节点 decompose judge 调用去掉搜索工具，减少 token 浪费。
- `MAARS_TEAM_MAX_DELEGATIONS` 默认值从 10 降为 5。

### 修复

- **严重：** `Stage.run` 不再将 FAILED 覆盖为 COMPLETED — Write 阶段不会在研究数据不完整时运行。
- **严重：** `max_iterations` 现在有硬性退出，防止无限策略更新循环。
- **高危：** Redecompose 后的依赖重连现在会持久化到 `plan_list.json`，防止恢复时 DAG 损坏。
- **高危：** `parse_json_fenced` 拒绝非 dict 的 JSON（如 `[...]`），不再传给假设 `.get()` 的调用者。
- **高危：** Decompose judge 在 `is_atomic: true` 时直接返回，即使 LLM 同时返回了 subtasks。
- **中等：** `CancelledError` 后 Stage 状态设为 IDLE，不再卡在 RUNNING。
- **中等：** `_load_checkpoint` 按 `plan_list.json` ID 过滤孤立任务输出。
- **中等：** `get_iteration` 只计数有效（非损坏）的评估文件。
- **低：** 前端输入框在启动失败后重新启用。

## 验证

- `python -m pytest tests/ -q` — 7 项通过
- 前端以仓库内静态资源形式交付，无需构建步骤。

**完整变更日志**: https://github.com/dozybot001/MAARS/compare/v13.5.0...v13.6.0

</details>

---

## MAARS 13.7.0 - Stage Reruns, Safer Writing, and Showcase Release `v13.7.0`

*发布于 2026-04-15*

## Summary

This release makes MAARS more usable for long-running research and publication workflows: stage-specific model overrides, deterministic research summaries for writing, safer stage reruns, tighter write/review completion rules, and a complete CIFAR-10→CIFAR-100 watermark-transfer showcase with final paper artifacts.

## Changes

### Added

- Stage-specific model overrides for `refine`, `research`, and `write`.
- Independent stage rerun support for workflows like write/rewrite without resetting the whole session.
- Deterministic `results_summary.json` / `results_summary.md` outputs for downstream writing.
- A full showcase run under `showcase/20260415-102608-showcase-phase-1-1-cifar10/` including artifacts, papers, and reproduction files.

### Changed

- Research decomposition guidance now accounts for both per-sandbox and per-agent-turn limits.
- Write stage now anchors on canonical results summaries and rewrites artifact paths for drafts/reviews/final paper automatically.
- Startup/config sanity checks now validate agent-session timeout against sandbox timeout.

### Fixed

- Final review rounds now complete consistently and stages no longer pass when reviewer approval is missing.
- Write-only reruns no longer wipe research artifacts from an existing session.
- Gemini model creation no longer forces built-in search, which previously broke external tool usage in write/rewrite runs.
- Session artifact rendering and modal display now resolve paper image paths correctly.
- Frontend pipeline completion and score/evaluation panel layout issues are fixed.

## Validation

- `python -m pytest tests -q` — 19 passed
- `bash start.sh` — startup smoke test passed with static frontend served successfully

**Full Changelog**: https://github.com/dozybot001/MAARS/compare/v13.6.0...v13.7.0

---

<details>
<summary>中文</summary>

## 摘要

本次发布重点增强了 MAARS 在长链路研究与论文交付场景下的可用性：支持阶段级模型覆盖、为写作阶段提供确定性的结果摘要、支持更安全的独立阶段重跑，并补齐了一个完整的 CIFAR-10→CIFAR-100 水印迁移 showcase 样例及最终论文产物。

## 变更内容

### Added

- 新增 `refine`、`research`、`write` 三个阶段的模型覆盖配置。
- 新增独立阶段重跑能力，可只重跑 write/rewrite，而无需重置整个 session。
- 新增确定性的 `results_summary.json` / `results_summary.md`，供下游写作直接消费。
- 新增完整 showcase 样例目录 `showcase/20260415-102608-showcase-phase-1-1-cifar10/`，包含实验产物、论文与复现文件。

### Changed

- Research 分解提示词现在同时考虑单次沙箱执行上限和单次 agent turn 上限。
- Write 阶段现在以 canonical results summary 为事实锚点，并自动修正草稿、review 与最终论文中的 artifact 路径。
- 启动与配置校验现在会检查 agent session timeout 与 sandbox timeout 的关系。

### Fixed

- 最终 review 轮次现在能稳定执行完成，缺少 reviewer 通过时阶段不再误判成功。
- 单独重跑 write 不会再清空已有 research artifacts。
- Gemini 模型创建不再强制开启内置 search，修复了 write/rewrite 运行时外部工具失效的问题。
- Session artifact 渲染与弹窗展示现在能正确解析论文中的图片路径。
- 前端流水线完成状态、score/evaluation 面板排版等问题已修复。

## 验证

- `python -m pytest tests -q` — 19 项通过
- `bash start.sh` — 启动冒烟测试通过，静态前端可正常提供服务

**完整变更日志**: https://github.com/dozybot001/MAARS/compare/v13.6.0...v13.7.0

</details>

---

## MAARS 13.7.1 — Bug Audit & Architecture Cleanup `v13.7.1`

*发布于 2026-04-15*

## MAARS 13.7.1 — Bug Audit & Architecture Cleanup

Three-round code audit: 11 bug fixes (including a path traversal security fix), architecture restructuring for better separation of concerns, and dead/duplicate code removal — all with zero behavior changes.

Net result: **-47 lines** (553 added, 600 removed across 17 files, 1 new module).

### Security

- `get_document` / `list_documents` endpoints now validate paths against the session root, preventing `../` traversal to read arbitrary `.md` files.

### Bug Fixes

- `clear_stage_outputs("research")` was a silent no-op — now correctly clears all research artifacts.
- `run_stage()` bypassed `ResearchStage.retry()`, leaving stale in-memory state on re-runs.
- `_depth()` in decompose confused task ID `"10"` with descendants of `"1"` (missing separator check).
- `_save_task` / `_execute_task` had missing None guards for `db` and `_api_semaphore`.
- `StageState` comparisons in routes used fragile string matching instead of enum identity.
- Prompt dispatchers inconsistently checked language setting.

### Architecture

- Extracted `results_summary.py` (~200 lines) from ResearchStage — 958→793 lines.
- Stage lifecycle API: `pause()` / `mark_completed()` / `configure()` / `prepare_resume()` replace direct attribute writes from orchestrator.
- Plan persistence centralized: `_all_tasks` as single source of truth, all mutations via `_persist_plan()` / `_update_task()`.
- ResearchDB: 4 internal helpers (`_get_text`/`_get_json`/`_save_text`/`_save_json`) reduce 20+ methods from 3-line boilerplate to 1-liners.
- `meta.json` read-modify-write protected by `threading.Lock`.
- `_api_semaphore` moved from global singleton to orchestrator instance attribute.
- Orchestrator/stages init moved into FastAPI `lifespan` handler.
- Docker sandbox container released on normal pipeline completion.
- Checkpoint recovery removed — pause/resume is memory-only.

**Full Changelog**: https://github.com/dozybot001/MAARS/compare/v13.7.0...v13.7.1

---

<details>
<summary>中文</summary>

## MAARS 13.7.1 — Bug 审查与架构清理

三轮代码审查：修复 11 个 bug（含路径穿越安全漏洞），重构架构以实现更清晰的职责分离，清除死代码和重复代码——零行为变更。

净变化：**-47 行**（17 个文件，新增 553，删除 600，1 个新模块）。

### 安全

- `get_document` / `list_documents` 端点现在校验路径不越出 session 根目录，防止 `../` 穿越读取任意 `.md` 文件。

### 问题修复

- `clear_stage_outputs("research")` 之前是空操作——现在正确清理所有 research 产物。
- `run_stage()` 绕过了 `ResearchStage.retry()`，重跑时内存残留旧状态。
- 分解模块 `_depth()` 字符串前缀匹配缺少 `_` 分隔符校验，`"10"` 被误认为 `"1"` 的后代。
- `_save_task` / `_execute_task` 缺少 `db` 和 `_api_semaphore` 的 None 保护。
- 路由中 `StageState` 比较使用脆弱的字符串匹配而非枚举。
- prompt dispatcher 语言检查不一致。

### 架构

- 提取 `results_summary.py`（~200 行）：ResearchStage 958→793 行。
- Stage 生命周期 API：`pause()` / `mark_completed()` / `configure()` / `prepare_resume()` 替代 orchestrator 直接写私有属性。
- 计划持久化集中化：`_all_tasks` 为内存唯一真值，所有修改走 `_persist_plan()` / `_update_task()`。
- ResearchDB：4 个内部 helper 将 20+ 个读写方法从 3 行样板精简为 1 行。
- `meta.json` 的 read-modify-write 加 `threading.Lock` 保护。
- `_api_semaphore` 从全局单例改为 orchestrator 实例属性。
- orchestrator/stages 初始化移入 FastAPI `lifespan` handler。
- Docker 沙箱容器在 pipeline 正常完成后自动释放。
- 移除断点恢复——暂停/继续仅使用内存状态。

**完整变更日志**: https://github.com/dozybot001/MAARS/compare/v13.7.0...v13.7.1

</details>

---

## MAARS 13.7.2 — Frontend Redesign `v13.7.2`

*发布于 2026-04-15*

## MAARS 13.7.2 — Frontend Redesign

Complete frontend overhaul: CSS cleanup, grayscale palette, and a structural redesign from generic dashboard to terminal-style research workstation.

Net result: **-41 lines** (164 added, 205 removed across 11 files).

### Layout

- Input bar moved to bottom with `>` prompt — terminal/REPL interaction pattern.
- Pipeline progress collapsed into a compact 36px status bar with inline dot labels.
- Panel headers and copy buttons removed — workspace is full-bleed between symmetric top/bottom bars.
- Same height (36px), padding (20px), and background for both bars.

### Visual System

- New grayscale palette: pure neutral grays replacing GitHub-dark blue tint.
- Status indicator colors (green/yellow/red/blue/purple/orange) retained as muted accents.
- Dual font system: system sans-serif for structural labels, monospace for data content.
- Removed `--accent` variable — all labels use `--text-primary` / `--text-secondary` gray scale.

### Cleanup

- Removed duplicate `@keyframes pulse`, merged split `.log-separator`, consolidated badge styles.
- Extracted shared `.exec-node::after` rule, deleted dead JS (`safeParse`, `STAGE_LABELS`, `wireCopyButton`).
- Merged SSE + Docker indicators into single system status dot (AND logic).
- Added responsive breakpoint (768px): stacked panels, hidden progress labels.
- Added `<link rel="icon">` for favicon.

**Full Changelog**: https://github.com/dozybot001/MAARS/compare/v13.7.1...v13.7.2

---

<details>
<summary>中文</summary>

## MAARS 13.7.2 — 前端重设计

前端全面重构：CSS 清理、灰阶配色、从通用 dashboard 布局重构为终端风格的研究工作站。

净变化：**-41 行**（11 个文件，新增 164，删除 205）。

### 布局

- 输入栏移至底部，带 `>` 提示符——终端/REPL 交互模式。
- 管道进度条压缩为 36px 紧凑状态栏，内联圆点+文字标签。
- 移除面板标题栏和复制按钮——工作区在上下对称栏之间全通栏显示。
- 上下栏完全对称：相同高度 (36px)、内边距 (20px)、背景色。

### 视觉体系

- 全新灰阶色板：纯中性灰替代原 GitHub Dark 蓝色调。
- 状态指示色（绿/黄/红/蓝/紫/橙）保留为低饱和度点缀。
- 双字体系统：系统 sans-serif 用于结构标签，monospace 用于数据内容。
- 移除 `--accent` 变量——所有标签使用 `--text-primary` / `--text-secondary` 灰阶。

### 清理

- 删除重复 `@keyframes pulse`，合并分散的 `.log-separator`，合并 badge 样式。
- 提取共用 `.exec-node::after` 规则，清除死代码（`safeParse`、`STAGE_LABELS`、`wireCopyButton`）。
- SSE + Docker 指示灯合并为单个系统状态点（AND 逻辑）。
- 新增响应式断点 (768px)：面板竖向堆叠、隐藏进度条文字。
- 补充 `<link rel="icon">` favicon 引用。

**完整变更日志**: https://github.com/dozybot001/MAARS/compare/v13.7.1...v13.7.2

</details>

---

## MAARS v13.8.0 — Website, Docs, and Demo Upgrade `v13.8.0`

*发布于 2026-04-17*

## Summary

This release turns MAARS into a much more polished project to evaluate and demo: it adds a GitHub Pages site, structured web docs, a teleprompter-driven recording flow, and a more stable Write/Polish pipeline. Net result: **+38,491 lines** across **120 files** since `v13.7.2`.

## Changes

### Added

- Added a GitHub Pages landing site with showcase sections, assets, and publish workflow.
- Added structured docs pages for architecture, Refine/Write, and Research under `site/docs/`.
- Added a teleprompter overlay and recording-oriented script flow for the demo experience.
- Added Lorenz and CIFAR showcase outputs, paper artifacts, and direct paper links from the site.

### Changed

- Refined the release-facing README and docs presentation to match the current three-stage MAARS workflow.
- Reworked the website and docs UX with language toggle support, sticky-offset fixes, improved mobile navigation, and cleaner inline code styling.
- Continued the Polish integration work so the final paper flow better matches the current Write-stage model and metadata output.

### Fixed

- Fixed docs scrollspy so sidebar and mobile TOC highlight the current section correctly.
- Fixed multiple GitHub Pages/mobile layout issues, including pipeline-card wrapping, nav behavior, and showcase link placement.
- Fixed several demo UX issues around teleprompter navigation, hero video behavior, and keyboard interaction.
- Synced tests with the current showcase path and TeamStage review semantics so release validation passes against the current implementation.

## Validation

- `PYTHONPATH=. pytest -q`
- `python3 -m compileall backend frontend site`
- `git pull --rebase origin main`

Full Changelog: https://github.com/dozybot001/MAARS/compare/v13.7.2...v13.8.0

---

## 摘要

这个版本把 MAARS 打磨成了一个更完整、也更适合展示的项目：新增 GitHub Pages 站点、结构化网页文档、面向录屏的 teleprompter 流程，以及更稳定的 Write/Polish 流水线。相对 `v13.7.2`，净变化为 **+38,491 行**，涉及 **120 个文件**。

## 变更内容

### Added

- 新增 GitHub Pages 落地页、showcase 展示区、站点资源以及自动发布工作流。
- 新增 `site/docs/` 下的结构化文档页面，覆盖 architecture、Refine/Write 和 Research。
- 新增用于演示录制的 teleprompter 浮层与脚本导航流程。
- 新增 Lorenz 与 CIFAR showcase 产物、论文文件，并在站点中提供直达论文入口。

### Changed

- 调整面向发布的 README 与文档呈现，使其与当前的三阶段 MAARS 工作流保持一致。
- 优化站点与 docs 的交互体验，包括语言切换、sticky 偏移修正、移动端导航，以及更稳的行内代码样式。
- 持续收敛 Polish 集成方式，使最终论文产出更贴合当前 Write 阶段与元数据附录逻辑。

### Fixed

- 修复 docs scrollspy，高亮状态现在会同时正确作用于侧边目录和移动端目录。
- 修复多处 GitHub Pages / 移动端布局问题，包括 pipeline 卡片换行、导航行为和 showcase 论文入口位置。
- 修复多处 demo 体验问题，包括 teleprompter 导航、hero 视频行为和键盘交互。
- 同步测试到当前的 showcase 路径与 TeamStage 审核语义，使发布验证能够基于现行实现通过。

## 验证

- `PYTHONPATH=. pytest -q`
- `python3 -m compileall backend frontend site`
- `git pull --rebase origin main`

完整变更日志: https://github.com/dozybot001/MAARS/compare/v13.7.2...v13.8.0

---

