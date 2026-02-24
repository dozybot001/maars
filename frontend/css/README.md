# 样式文件说明

MAARS 前端采用模块化 CSS 结构，便于维护与扩展。

## 入口

- **`../styles.css`**：主入口，通过 `@import` 引入 `css/` 下各模块

## 模块划分

| 文件 | 说明 |
|------|------|
| `theme.css` | 主题色板（light/dark/black），定义颜色变量 |
| `base.css` | 全局变量（`:root`）、reset、滚动条、body、container |
| `layout.css` | 页头、区块通用样式、排版、主题切换按钮 |
| `planner.css` | Planner 区块：想法输入、AI 思考区、Markdown 渲染 |
| `monitor.css` | Monitor 区块：时间表区域、diagram 容器 |
| `components.css` | 通用组件：按钮、modal、表单、任务详情 popover |
| `api-config.css` | API 配置弹窗及其内部表单 |
| `task-tree.css` | 任务树：执行图、timetable 网格、树节点、连接线 |
| `executor.css` | Executor 区块：执行器列表与状态 |
| `validator.css` | Validator 区块：验证器列表与状态 |

## 加载顺序

```
theme.css → base.css → layout.css → planner.css → monitor.css
         → components.css → api-config.css → task-tree.css
         → executor.css → validator.css
```

主题需最先加载以提供颜色变量；其余按页面结构自上而下。
