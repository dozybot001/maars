# MAARS 开发指南

面向后续开发的详细指南，涵盖底层架构、工作流、Skill 扩充与维护等。

---

## 一、底层架构

### 1.1 整体架构

```text
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (静态页面)                       │
│  flows (idea/plan/task/paper) + thinking + output + websocket    │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP POST 触发 / WebSocket 数据回传
┌──────────────────────────────▼──────────────────────────────────┐
│                         Backend (FastAPI + Socket.io)            │
│  api/routes → idea_agent / plan_agent / task_agent / paper_agent │
└──────────────────────────────┬──────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                       ▼
┌───────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ shared/       │    │ db/             │    │ visualization/  │
│ llm_client    │    │ 文件存储         │    │ 执行图布局       │
│ skill_utils   │    │ idea_id/plan_id/│    │                 │
│ adk_bridge    │    │ settings.json   │    │                 │
│ reflection    │    │                 │    │                 │
└───────────────┘    └─────────────────┘    └─────────────────┘
```

### 1.2 四 Agent 统一流程模型

```text
用户点击 → HTTP POST 触发 → 后端后台任务 → WebSocket 数据回传 → 前端更新 UI
```

- **HTTP**：仅用于触发，立即返回 `{success, id}`
- **WebSocket**：所有流式数据、完成状态、错误均由后端推送
- **前端**：不依赖 HTTP 响应，仅用 WebSocket 事件更新 UI

### 1.3 三模式架构

| 模式 | 说明 | 入口 |
| --- | --- | --- |
| **Mock** | 模拟输出，不调用真实 LLM | `*UseMock=True`，走 mock_chat_completion |
| **LLM** | 固定步骤 + 单轮 chat_completion | collect_literature / 递归分解 / execute_task |
| **Agent** | Google ADK 驱动，工具循环 | adk_runner.run_*_agent_adk |

Mock 与 LLM 共用 LLM 管道；Agent 模式单独走 Google ADK。

### 1.4 Agent 目录结构

```text
{agent}/
├── agent.py           # Agent 入口，*AgentMode=True 时调用
├── adk_runner.py      # Google ADK 驱动（仅 Agent 模式）
├── agent_tools.py     # 工具定义 + execute 逻辑
├── llm/               # 单轮 LLM（Mock/LLM 模式）
│   └── executor.py
├── prompts/           # {agent}-agent-prompt.txt、reflect-prompt.txt
├── skills/            # Agent Skills
│   └── {skill-name}/
│       ├── SKILL.md   # 入口，YAML frontmatter + Markdown
│       ├── scripts/   # 可执行脚本（仅 Task Agent）
│       └── references/# 参考文档
└── __init__.py
```

### 1.5 共享模块职责

| 模块 | 职责 |
| --- | --- |
| `shared/llm_client` | chat_completion、merge_phase_config |
| `shared/skill_utils` | list_skills、load_skill、read_skill_file |
| `shared/adk_bridge` | ExecutorTool、create_executor_tools、prepare_api_env |
| `shared/reflection` | self_evaluate、generate_skill、reflection_loop、save_learned_skill |
| `shared/constants` | REFLECT_MAX_ITERATIONS、REFLECT_QUALITY_THRESHOLD 等 |

---

## 二、工作流说明

### 2.1 Idea Agent

**流程**：用户 idea → Keywords（流式）→ arXiv 检索 → Refine（流式）→ 保存 idea

**工具**（Agent 模式）：ExtractKeywords、SearchArxiv、EvaluatePapers、FilterPapers、AnalyzePapers、RefineIdea、ValidateRefinedIdea、FinishIdea、ListSkills、LoadSkill、ReadSkillFile

**Skill 用途**：关键词提取、文献评估、refined idea 质量等

### 2.2 Plan Agent

**流程**：idea → 递归：Atomicity → [Decompose | Format] → Quality 评估 → 任务树

**工具**（Agent 模式）：CheckAtomicity、Decompose、FormatTask、AddTasks、UpdateTask、GetPlan、GetNextTask、FinishPlan、ListSkills、LoadSkill、ReadSkillFile

**Skill 用途**：分解模式、研究范围、格式规范、依赖规则等

### 2.3 Task Agent

**流程**：任务依赖满足 → Execute → Validate → artifact

**工具**（Agent 模式）：ReadArtifact、ReadFile、WriteFile、WebSearch、WebFetch、Finish、ListSkills、LoadSkill、ReadSkillFile、RunSkillScript

**Skill 用途**：输出格式（markdown-reporter、json-utils）、验证（task-output-validator）、调研（web-research、literature-synthesis）等

### 2.4 Paper Agent

**流程**：Plan + Task 产出 → 单轮 LLM 生成 → 论文草稿

**说明**：当前仅 Mock/LLM 模式，Agent 模式待开发

---

## 三、Skill 体系

### 3.1 Skill 结构

```text
{agent}/skills/{skill-name}/
├── SKILL.md           # 必需，入口文件
├── scripts/           # 可选，可执行脚本（仅 Task Agent）
│   └── validate.py
└── references/        # 可选，参考文档
    └── examples.md
```

### 3.2 SKILL.md 规范

**YAML frontmatter**（必需）：

```yaml
---
name: skill-name
description: 简短描述，用于 ListSkills 展示和 LoadSkill 触发条件
---
```

**可选字段**（Learned Skill 自动添加）：

```yaml
source: learned
created_at: "2024-01-15T12:00:00"
agent_type: idea | plan | task
```

**正文**：Markdown，说明何时使用、如何应用、示例等。

### 3.3 Skill 发现与加载

| 操作 | 实现 | 说明 |
| --- | --- | --- |
| 发现 | `shared/skill_utils.list_skills(skills_root)` | 扫描 skills 目录，返回 `[{name, description}]` |
| 加载 | `shared/skill_utils.load_skill(skills_root, name)` | 读取 SKILL.md 全文 |
| 读文件 | `shared/skill_utils.read_skill_file(skills_root, skill, path)` | 读取 skill 目录下的 references/、scripts/ 等 |

**环境变量**（可选）：

- `MAARS_IDEA_SKILLS_DIR`、`MAARS_PLAN_SKILLS_DIR`、`MAARS_TASK_SKILLS_DIR`：覆盖默认 skills 路径

### 3.4 Task Agent 专属：RunSkillScript

**支持扩展名**：`.py`、`.sh`、`.js`

**执行**：脚本在 skill 目录下以 `cwd` 运行，`{{sandbox}}` 在 args 中替换为任务沙箱路径

**超时**：`MAARS_RUN_SCRIPT_TIMEOUT`（默认 120 秒）

**示例**：

```text
RunSkillScript(skill="task-output-validator", script="scripts/validate.py",
  args=["{{sandbox}}/output.json", "--criteria-json", "<JSON>"])
```

---

## 四、Skill 扩充指南

### 4.1 新增 Skill 步骤

1. **创建目录**：`{agent}/skills/{skill-name}/`
2. **编写 SKILL.md**：
   - 填写 `name`、`description`（description 要具体，便于 Agent 判断何时加载）
   - 正文说明 When to Apply、Instructions、Examples
3. **（可选）添加 references/**：如 `references/templates.md`、`references/examples.md`
4. **（Task Agent 可选）添加 scripts/**：如 `scripts/validate.py`，需符合 RunSkillScript 规范

### 4.2 SKILL.md 撰写要点

- **description**：决定 ListSkills 展示和 Agent 何时 LoadSkill，应包含触发条件关键词
- **When to Apply**：明确什么场景下应加载此 skill
- **Instructions**：分步骤、可执行，避免模糊表述
- **Examples**：至少一个具体示例
- **引用**：可用 `[references/xxx.md](references/xxx.md)` 链接到参考文档

### 4.3 各 Agent Skill 类型参考

| Agent | 典型 Skill 类型 | 示例 |
| --- | --- | --- |
| Idea | 关键词提取、文献评估、refined idea 质量 | keyword-extraction、refined-idea-quality |
| Plan | 分解模式、研究范围、格式规范、依赖规则 | decomposition-patterns、format-specs、dependency-rules |
| Task | 输出格式、验证、调研、分析 | markdown-reporter、task-output-validator、literature-synthesis |

### 4.4 带脚本的 Skill（Task Agent）

1. 在 skill 目录下创建 `scripts/`，如 `scripts/validate.py`
2. 在 SKILL.md 中说明调用方式、参数、输出格式
3. 脚本需：
   - 可独立运行（不依赖项目其他模块，或仅依赖 requirements.txt）
   - 通过 stdout 返回结果
   - 控制执行时间，避免长时间阻塞

---

## 五、Skill 维护

### 5.1 Learned Skill

Self-Reflection 启用时，低分输出可触发 `generate_skill_from_reflection`，生成并保存到 `{agent}/skills/learned-xxx/` 或 `{skill-name}-{timestamp}/`。

**frontmatter**：自动添加 `source: learned`、`created_at`、`agent_type`

**维护**：定期检查 learned 目录，合并重复、删除过时、提炼通用 skill

### 5.2 Skill 更新流程

1. 修改 SKILL.md 或 references/、scripts/
2. 无需重启服务，Agent 下次 LoadSkill 时读取最新内容
3. 若修改了脚本，确保兼容既有调用方式

### 5.3 Skill 测试

- **ListSkills**：确认新 skill 出现在列表中
- **LoadSkill**：在 Agent 模式下让 Agent 加载，检查是否按预期使用
- **RunSkillScript**：对带脚本的 skill，可单独运行脚本验证

---

## 六、Self-Reflection 与 Skill 生成

### 6.1 流程

```text
Agent 执行主任务 → self_evaluate（LLM 评分）→ score >= threshold? → 完成
                                        ↓ No（迭代未满）
                                 generate_skill_from_reflection
                                        ↓
                                 save_learned_skill → 重新执行 → self_evaluate ...
```

### 6.2 评估维度

| Agent | 维度 |
| --- | --- |
| Idea | 新颖性、研究空白、可行性、科研价值 |
| Plan | MECE、依赖合理性、粒度、清晰度、可执行性 |
| Task | 完整性、深度、准确性、格式符合度 |

### 6.3 配置

Settings → AI Config → Self-Reflection：

- **enabled**：是否启用
- **maxIterations**：最大反思重执行次数（默认 2）
- **qualityThreshold**：质量分阈值（默认 70，0–100）

### 6.4 实现位置

| 模块 | 文件 |
| --- | --- |
| 统一框架 | `shared/reflection.py` |
| Skill 生成 prompt | `shared/prompts/skill-generation-prompt.txt` |
| 接入点 | `api/routes/idea.py`、`api/routes/plan.py`、`task_agent/runner.py` |

---

## 七、扩展开发检查清单

### 7.1 新增 Agent

1. 遵循 `agent-structure` 目录规范
2. 实现 `{prefix}-start`、`{prefix}-thinking`、`{prefix}-error`、`{prefix}-complete`
3. 支持 Stop（abort_event、立即恢复按钮）
4. 前端 flow 派发 `maars:{prefix}-start`，监听 `maars:{prefix}-complete`，暴露 reset 方法

### 7.2 新增 Skill

1. 创建 `{agent}/skills/{skill-name}/SKILL.md`
2. 填写 name、description
3. 正文包含 When to Apply、Instructions、Examples
4. （Task Agent）如需脚本，添加 scripts/ 并符合 RunSkillScript 规范

### 7.3 新增工具（Agent 模式）

1. 在 `agent_tools.py` 的 TOOLS 列表添加定义（OpenAI function-calling 格式）
2. 在 `execute_tool` 或对应分支实现执行逻辑
3. 若用 ADK：`create_executor_tools` 会自动转换，无需额外代码

### 7.4 修改工作流

1. 检查四个 Agent 的对称性（见 `.cursor/rules/agent-flow-architecture.mdc`）
2. 更新 `docs/workflow/` 下对应文档

---

## 八、相关文档

| 文档 | 说明 |
| --- | --- |
| [docs/workflow/](workflow/README.md) | 工作流说明 |
| [docs/design/agent-structure.md](design/agent-structure.md) | Agent 目录结构 |
| [docs/design/region-responsibilities.md](design/region-responsibilities.md) | Thinking/Output 区域职责 |
| [.cursor/rules/agent-flow-architecture.mdc](../.cursor/rules/agent-flow-architecture.mdc) | Agent 流程与架构规则 |
