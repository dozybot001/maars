# 前端脚本与模块依赖

`frontend/index.html` 中脚本加载顺序及模块依赖。

## 加载顺序

```
Socket.io → marked → DOMPurify → highlight.js  (第三方库)
    ↓
utils.js          # 工具函数 (escapeHtml, escapeHtmlAttr)，无依赖
    ↓
task-tree.js      # 任务树渲染，依赖 utils
    ↓
config.js         # API/存储配置，创建 window.MAARS
    ↓
constants.js      # 魔法数字集中管理 (RENDER_THROTTLE_MS 等)，无依赖
    ↓
theme.js          # 主题切换、API 配置模态框，依赖 config, utils
    ↓
api.js            # API 客户端，依赖 config
    ↓
planner.js        # 规划器 UI，依赖 config, api
    ↓
thinking-area.js  # createThinkingArea 工厂，无依赖
    ↓
planner-thinking.js   # 依赖 thinking-area, config
executor-thinking.js  # 依赖 thinking-area, config（Execute/Validate 合并）
    ↓
monitor.js        # 时间表、Executor chips，依赖 config, api, utils
    ↓
websocket.js      # Socket.io 事件分发，依赖 config, planner, monitor, plannerThinking, executorThinking
    ↓
app.js            # 入口，组装各模块
```

## 模块依赖图

```
                    config
                      │
        ┌─────────────┼─────────────┐
        │             │             │
     theme          api         planner
        │             │             │
        └─────────────┴─────────────┘
                      │
              thinking-area
                      │
        ┌─────────────┴─────────────┐
        │                           │
planner-thinking            executor-thinking (Execute + Validate)
        │                           │
        └─────────────┬─────────────┘
                      │
                  monitor  ←── utils, task-tree
                      │
                 websocket
                      │
                    app
```

## 关键依赖说明

| 模块 | 依赖 | 说明 |
|------|------|------|
| utils | 无 | 必须最先加载（在 task-tree 之前） |
| task-tree | utils | 弹窗中 escapeHtml 用于安全渲染 |
| theme | config, utils | API 配置模态框 |
| websocket | planner, monitor, plannerThinking, executorThinking | 所有 thinking 模块必须在 websocket 之前加载 |

## window.MAARS.state 结构

各模块应仅读写自身命名空间，避免隐式依赖：

| 命名空间 | 模块 | 说明 |
|----------|------|------|
| `socket` | websocket | Socket.io 实例 |
| `timetableLayout` | monitor | 时间表布局 |
| `chainCache` | monitor | 执行链缓存 |
| `previousTaskStates` | monitor | 任务状态变更追踪 |
| `executorOutputs` | executor-thinking | 任务输出 |
| `*ThinkingBlocks` | thinking-area | 各 thinking 区域块 |
| `*ThinkingUserScrolled` | thinking-area | 用户滚动状态 |

## 注意

- thinking 模块必须在 websocket 之前
- utils 必须在 task-tree 之前
