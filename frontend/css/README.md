# 样式文件

主入口 `../styles.css` 通过 `@import` 引入各模块。theme 最先加载以提供颜色变量。

## 模块

| 文件 | 说明 |
|------|------|
| `theme.css` | 主题色板（light/dark/black），定义颜色变量 |
| `base.css` | 全局变量（`:root`）、reset、滚动条、body、container |
| `layout.css` | 页头、区块通用样式、排版、主题切换按钮 |
| `planner.css` | Planner 区块：想法输入、AI 思考区、Markdown 渲染 |
| `monitor.css` | Monitor 区块：时间表区域、diagram 容器 |
| `components.css` | 通用组件：按钮、modal、表单、任务详情 popover（按钮规范见 [BUTTON_DESIGN.md](BUTTON_DESIGN.md)） |
| `api-config.css` | API 配置弹窗及其内部表单 |
| `task-tree.css` | 任务树：执行图、timetable 网格、树节点、连接线 |
| `executor.css` | Executor 区块：执行器列表与状态 |
| `validator.css` | Validator 区块：验证器列表与状态 |
