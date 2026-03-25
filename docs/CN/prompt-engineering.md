# Prompt 工程文档

## Prompt 分层架构

MAARS 的 prompt 分为两层，各司其职：

```
┌─────────────────────────────────────────┐
│ 适配器层 Instruction（Agent 独有）        │
│ 职责：工具使用、行为约束、语言偏好        │
│ 位置：backend/agent/__init__.py          │
│ 注入：create_agent(instruction=...)      │
├─────────────────────────────────────────┤
│ Pipeline 层 System Prompt（三模式共用）   │
│ 职责：流程指令、轮次目标、自动化约束       │
│ 位置：backend/pipeline/*.py              │
│ 注入：build_messages() 的 system role    │
└─────────────────────────────────────────┘
```

### 合并机制

Gemini 模式：pipeline system prompt 直接作为 `system_instruction`，无适配器层。

Agent 模式：`AgentClient._build_agent_prompt()` 将两层合并为统一的 ADK system instruction：

```
merged_instruction = 适配器 instruction + "\n\n" + pipeline system prompt
```

Agent 收到的完整结构：
```
[ADK System Instruction]            ← merged_instruction
  适配器指令（工具、行为）
  +
  Pipeline 指令（流程、轮次目标）

[User Message]                      ← user_prompt
  用户输入 / 历史对话 / 阶段指令
```

## Pipeline 层 Prompt 清单

### 通用前缀

所有 pipeline prompt 共享 `_AUTO` 前缀：

```
This is a fully automated pipeline. No human is in the loop.
Do NOT ask questions or request input. Make all decisions autonomously.
全文使用中文撰写。
```

### Refine（3 轮）

| 轮次 | 标签 | 目标 |
|------|------|------|
| 0 | Explore | 发散：识别子领域、调研现状、发散方向 |
| 1 | Evaluate | 收敛：三维评估（新颖性/可行性/影响力），选定方向 |
| 2 | Crystallize | 产出：完整研究提案（标题/问题/方法/贡献） |

位置：`backend/pipeline/refine.py` → `_PROMPTS[]`

### Plan（模板 + 可替换原子定义）

模板 `_SYSTEM_PROMPT_TEMPLATE` 包含：
- 流水线上下文（4 阶段说明，Write 阶段负责写论文）
- `{atomic_definition}` 占位符 ← 适配器注入
- 规则：依赖、并行、JSON 格式

原子定义由模式决定：

| 模式 | 原子标准 |
|------|---------|
| Gemini/Mock | 单次 LLM 调用能产出可靠结果 |
| Agent | 单个 Agent session 能端到端完成（含多次工具调用） |

位置：`backend/pipeline/plan.py` → `_SYSTEM_PROMPT_TEMPLATE` + `_ATOMIC_DEF_DEFAULT`
Agent 原子定义：`backend/agent/__init__.py` → `agent_atomic_def`

### Execute（2 个 prompt）

| Prompt | 用途 |
|--------|------|
| `_EXECUTE_SYSTEM` | 任务执行：产出有深度的结果 |
| `_VERIFY_SYSTEM` | 质量验证：判断是否实质达成目标（务实不教条） |

位置：`backend/pipeline/execute.py`

### Write（3 个 prompt）

| Prompt | 阶段 | 用途 |
|--------|------|------|
| `_OUTLINE_SYSTEM` | Outline | 设计论文大纲，映射任务到章节 |
| `_SECTION_SYSTEM` | Sections | 基于任务产出写单个章节 |
| `_POLISH_SYSTEM` | Polish | 润色全文，统一术语和风格 |

位置：`backend/pipeline/write.py`

## 适配器层 Instruction 清单

仅 Agent 模式有适配器指令。Gemini/Mock 不需要（pipeline prompt 够用）。

| 指令 | 用于阶段 | 核心内容 |
|------|---------|---------|
| `_REFINE_INSTRUCTION` | Refine | 列出可用工具，指导搜索论文流程 |
| `_EXECUTE_INSTRUCTION` | Execute | **强制使用工具**：MUST call code_execute，不伪造 |
| `_WRITE_INSTRUCTION` | Write | 列出 DB 工具，指导读取任务产出写论文 |
| `agent_atomic_def` | Plan | Agent 的原子任务定义（注入 Plan 模板） |

位置：`backend/agent/__init__.py`

## 完整 Prompt 示例

### Agent 模式 — Refine Explore 轮

```
[ADK System Instruction]
You have access to research tools. Use them to ground your analysis...
Available tools: Google Search, arXiv, fetch...
全文使用中文撰写。

This is a fully automated pipeline. No human is in the loop.
Do NOT ask questions or request input. Make all decisions autonomously.

You are a research advisor helping to explore a vague research idea.
Given the user's initial idea, your job is to:
- Identify the core research domain...
Be expansive and creative.
Output in markdown.

[User Message]
用 Python 生成并可视化分形图案：比较 Mandelbrot 集与 Julia 集的结构差异
```

### Agent 模式 — Execute 某任务

```
[ADK System Instruction]
You have access to research and experiment tools. You MUST use them...
CRITICAL RULES: When a task involves code, you MUST call code_execute...
全文使用中文撰写。

This is a fully automated pipeline...
You are a research assistant executing a specific task...
Produce a thorough, well-structured result...
Output in markdown.

[User Message]
## Prerequisite tasks (use read_task_output to read): 1_1, 1_2
---
## Your task [2_1]:
实现 Mandelbrot 集的逃逸时间算法并生成高分辨率可视化图像
```

### Gemini 模式 — Execute 某任务

```
[System Instruction]
This is a fully automated pipeline...
You are a research assistant executing a specific task...
Output in markdown.

[User Message]
## Context from completed prerequisite tasks:
### Task [1_1] output:
（完整的依赖任务内容，预加载在 prompt 中）
---
## Your task [2_1]:
实现 Mandelbrot 集的逃逸时间算法并生成高分辨率可视化图像
```

## 修改指南

| 要改什么 | 改哪里 |
|---------|--------|
| 全局自动化约束 | `pipeline/refine.py` 的 `_AUTO`（其他文件同名变量） |
| 某阶段的流程逻辑 | 对应的 `pipeline/*.py` |
| Agent 的工具使用指导 | `agent/__init__.py` 的 `_*_INSTRUCTION` |
| 原子任务标准 | Gemini: `pipeline/plan.py` 的 `_ATOMIC_DEF_DEFAULT`；Agent: `agent/__init__.py` 的 `agent_atomic_def` |
| 语言偏好 | `pipeline/*.py` 的 `_AUTO` 前缀（全局生效） |
| Verify 严格度 | `pipeline/execute.py` 的 `_VERIFY_SYSTEM` |
