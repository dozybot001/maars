# Executor 改进规划

本文档记录 Executor 模块的改进方向，供后续迭代开发参考。当前 Executor 为单次 LLM 调用，规划升级为 Agent 形态并接入 Agent Skills。

---

## 一、Executor 升级为 Agent

### 1.1 现状

- 单次 LLM 调用：`execute_task` 一次 chat completion 生成输出
- 无工具调用、无多轮、无脚本执行
- 纯文本生成，通用性有限

### 1.2 目标架构

Executor 设计为**小型 Agent**，支持多轮 LLM 调用与工具调用：

```
任务输入 (description, input artifacts, output spec)
    ↓
Agent 循环:
    LLM 决策 → 可选动作: [继续生成] | [调用工具] | [结束]
    ↓
工具: LoadSkill, ReadFile, RunScript, WebSearch, ...
    ↓
工具结果返回 LLM → 下一轮
    ↓
满足 output spec 后结束，返回结果
```

### 1.3 与现有流程衔接

- **Planner**：继续负责分解，产出原子任务（含 input/output spec）
- **Executor Agent**：对每个原子任务，以 Agent 循环执行，可多次 LLM 调用、多次工具调用
- **Artifact**：Agent 完成后的输出仍写入 `db/{plan_id}/{task_id}/output.json`，下游任务照常消费

---

## 二、Agent Skills 接入

### 2.1 项目背景

[Agent Skills](https://agentskills.io) 是 Anthropic 开源的能力扩展格式，由 [agentskills/agentskills](https://github.com/agentskills/agentskills) 维护。

- **格式**：Skill = 目录 + `SKILL.md`（YAML frontmatter + Markdown 指令）+ 可选 `scripts/`、`references/`、`assets/`
- **流程**：Discover → Load metadata → Match → Activate → Execute

### 2.2 与 Executor Agent 的对应关系

| Agent Skills 流程 | Executor Agent 中的实现 |
|-------------------|-------------------------|
| Discover | 启动时扫描 `skills/` 目录 |
| Load metadata | 解析各 skill 的 frontmatter，生成技能列表 |
| Match | 根据任务描述，由 LLM 或规则选出相关 skills |
| Activate | 通过 `LoadSkill` 工具加载完整 SKILL.md |
| Execute | Agent 按 skill 指令执行，需要时调用 `RunScript` 等工具 |

### 2.3 工具设计

| 工具 | 用途 |
|------|------|
| `ListSkills()` | 返回可用 skill 的 name + description，供 LLM 选择 |
| `LoadSkill(name)` | 加载指定 skill 的 SKILL.md 全文，注入当前上下文 |
| `ReadSkillFile(skill, path)` | 读取 skill 的 `references/`、`assets/` 等文件 |
| `RunSkillScript(skill, script, args)` | 在受控环境中执行 skill 的 `scripts/` 下脚本 |

### 2.4 实现要点

- **技能目录**：配置 skills 根目录（如 `backend/skills/` 或环境变量）
- **skills-ref**：使用 [skills-ref](https://github.com/agentskills/agentskills/tree/main/skills-ref) 做校验、元数据解析、生成 prompt 片段
- **沙箱**：`RunSkillScript` 应在隔离环境执行（如 subprocess + 资源限制）
- **终止条件**：Agent 需能判断何时满足 output spec 并结束，避免无限循环

---

## 三、Atomicity 与 Executor 能力边界

### 3.1 设计原则

**Atomicity 的边界应随 Executor 的能力边界变化**。

| Executor 形态 | 一次「执行单元」能做的事 | 可视为原子的任务范围 |
|---------------|--------------------------|------------------------|
| 单次 LLM 调用 | 纯文本生成 | 较窄 |
| Agent（多轮 + 工具） | 多次 LLM + 工具调用 | 更宽 |
| Agent + Skills | 还能加载技能、跑脚本 | 更宽 |

- Executor 越强 → 一次执行能完成更多子步骤 → 可视为原子的任务可以更「粗」
- Executor 越弱 → 需要 Planner 把任务拆得更细

### 3.2 后续调整方向

1. **Atomicity prompt**：将「单步可执行」改为「在 Executor 当前能力下可一次完成」
2. **上下文**：在 atomicity 判断时传入 Executor 能力描述（例如：支持工具、Skills、多轮等）
3. **可配置**：通过配置切换「保守 / 宽松」的 atomicity 策略，对应不同 Executor 版本

---

## 四、优先级建议

| 优先级 | 项目 | 理由 |
|--------|------|------|
| P1 | Executor Agent 化 | 多轮 + 工具调用是基础能力 |
| P1 | Agent Skills 接入（指令注入） | 先实现 LoadSkill + 指令注入，无需脚本 |
| P2 | RunSkillScript 工具 | 完整支持 scripts/ |
| P2 | Atomicity 与 Executor 能力边界联动 | 分解粒度与执行能力对齐 |
| P3 | 其他工具（WebSearch、ReadFile 等） | 按需扩展 |

---

## 五、参考

- [Agent Skills 规范](https://agentskills.io/specification)
- [Agent Skills 集成指南](https://agentskills.io/integrate-skills.md)
- [agentskills/agentskills](https://github.com/agentskills/agentskills)
- [anthropics/skills 示例](https://github.com/anthropics/skills)
