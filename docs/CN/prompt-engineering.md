# Prompt 工程文档

## Prompt 架构

MAARS 有两套 prompt 体系：

```
Gemini/Mock 模式                     Agent 模式（ADK/Agno）
─────────────                       ─────────────────────
Pipeline System Prompt               Agent Instruction
  职责：流程编排、轮次目标              职责：完整任务描述、工具使用约束
  位置：backend/pipeline/*.py          位置：backend/agent/__init__.py
  注入：build_messages() system role           backend/agno/__init__.py
                                     注入：AgentClient/AgnoClient(instruction=...)
```

### 设计原则

- **Gemini/Mock**：无工具，pipeline 通过多轮 prompt 手把手编排
- **Agent**：有工具，instruction 描述完整任务目标，Agent 自主决定步骤
- **Research 阶段**：两种模式共用 `ResearchStage`，prompt 由 pipeline 统一管理
- **Calibrate**：prompt 由 pipeline 管理，但通过 `stream()` 执行——Agent 模式下是完整 agent session

## Pipeline 层 Prompt 清单

### 通用前缀

```
_AUTO = "This is a fully automated pipeline. No human is in the loop.
Do NOT ask questions or request input. Make all decisions autonomously.
全文使用中文撰写。"
```

### Refine（3 轮）

| 轮次 | 标签 | 目标 |
|------|------|------|
| 0 | Explore | 发散：识别子领域、调研现状、发散方向 |
| 1 | Evaluate | 收敛：三维评估（新颖性/可行性/影响力），选定方向 |
| 2 | Crystallize | 产出：完整研究提案 |

位置：`backend/pipeline/refine.py` → `_PROMPTS[]`

### Calibrate（动态能力校准）

Research 阶段的 Phase 0。让 LLM/Agent 自评能力边界，生成原子任务定义。

```
_CALIBRATE_SYSTEM:
- 评估自身能力
- 允许试用工具验证可用性
- 输出简洁的 ATOMIC DEFINITION block（3-5 句）
  - 单次 session 能完成什么
  - 此研究领域的原子任务示例
  - 需要分解的任务示例
```

位置：`backend/pipeline/research.py` → `_CALIBRATE_SYSTEM`

输入：`describe_capabilities()` 返回的能力描述 + 研究主题

### Decompose（模板 + 动态原子定义）

模板 `_SYSTEM_PROMPT_TEMPLATE` 包含：
- 流水线上下文（Research + Write 两阶段说明）
- `{atomic_definition}` 占位符 ← Calibrate 阶段的输出
- 规则：依赖、并行、JSON 格式、何时停止分解

位置：`backend/pipeline/decompose.py` → `_SYSTEM_PROMPT_TEMPLATE`

原子定义来源：
- 由 Calibrate 动态生成（不再硬编码）
- 空字符串时分解仍能工作（LLM 用通用判断力决定）

### Execute + Verify（3 个 prompt）

| Prompt | 用途 |
|--------|------|
| `_EXECUTE_SYSTEM` | 任务执行：产出实质结果，不是描述 |
| `_VERIFY_SYSTEM` | 三路验证：pass / retry / redecompose |
| `_CALIBRATE_SYSTEM` | 能力校准（见上） |

Verify prompt 的 redecompose 判断指引：

```
Set "redecompose" to true ONLY when:
- 任务覆盖多个独立子目标，结果浅尝辄止
- 结果显示任务范围超出单次 session 能力
- 方法论根本错误（不是仅仅不完整）
```

位置：`backend/pipeline/research.py`

### Write（5 阶段）

| Prompt | 阶段 | 用途 |
|--------|------|------|
| `_OUTLINE_SYSTEM` | Outline | 设计论文大纲，映射任务到章节，分配图表 |
| `_SECTION_SYSTEM` | Sections | 基于分配的任务产出写单个章节 |
| `_STRUCTURE_SYSTEM` | Structure | 交叉一致性：数字、术语、论断 |
| `_STYLE_SYSTEM` | Style | 学术风格润色 + References |
| `_FORMAT_SYSTEM` | Format | 格式规范：图表编号、引用、层级 |

位置：`backend/pipeline/write.py`

## Agent Instruction 清单

Agent 模式的 Refine 和 Write 使用独立 stage，instruction 是完整任务描述，不拼接 pipeline prompt。

| 指令 | 用于阶段 | Stage 类 | 核心内容 |
|------|---------|---------|---------|
| `_REFINE_INSTRUCTION` | Refine | `AgentRefineStage` | Explore → Evaluate → Crystallize，强制使用搜索工具 |
| `_EXECUTE_INSTRUCTION` | Research | `ResearchStage`（共用） | **强制工具使用**：MUST call code_execute |
| `_WRITE_INSTRUCTION` | Write | `AgentWriteStage` | 读取所有产出、设计结构、撰写全文、嵌入图表 |

位置：`backend/agent/__init__.py`、`backend/agno/__init__.py`

**注意**：Research 阶段的 Calibrate/Decompose/Verify prompt 来自 `pipeline/research.py`（所有模式共用），Execute instruction 来自 Agent mode init（Agent 专用）。两者通过 `AgentClient._build_agent_prompt()` 合并。

## 完整 Prompt 示例

### Agent 模式 — Calibrate

```
[System = _CALIBRATE_SYSTEM]
This is a fully automated pipeline...
You are calibrating task decomposition for a research pipeline.
Assess your own capabilities...

[User]
## Your Capabilities
AI Agent (ADK) with multi-step reasoning. Model: gemini-2.0-flash
Available tools:
- google_search
- url_context
- code_execute: Run Python code in Docker sandbox
- read_task_output: Read completed task output
- list_artifacts: List generated files

## Research Topic
蒙特卡洛方法估算圆周率：不同采样策略对收敛速度的影响
```

### Agent 模式 — Execute（redecompose 子任务）

```
[System = _EXECUTE_INSTRUCTION + _EXECUTE_SYSTEM 合并]

[User]
## Context from completed prerequisite tasks:
### Task [1_1] output:
（依赖任务的内容）
---
## Prior attempt on parent task (reference only — focus on YOUR specific subtask):
（父任务 2_1 的 partial output — 之前尝试但不充分的结果）
---
## Your task [2_1_d1]:
实现基础蒙特卡洛采样算法并测试 1000-100000 样本范围的收敛行为
```

### Gemini 模式 — Verify

```
[System = _VERIFY_SYSTEM]
You are a research quality reviewer...
Respond with ONLY a JSON object:
If acceptable: {"pass": true, "summary": "..."}
If minor issues: {"pass": false, "redecompose": false, "review": "..."}
If fundamentally too complex: {"pass": false, "redecompose": true, "review": "..."}

[User]
Task [2_1]: 对比三种蒙特卡洛采样策略的收敛性能
--- Execution result ---
（任务执行结果）
```

## 修改指南

| 要改什么 | 改哪里 |
|---------|--------|
| Gemini/Mock Refine 流程 | `pipeline/refine.py` → `_PROMPTS[]` |
| Agent Refine/Write 任务描述 | `agent/__init__.py` 或 `agno/__init__.py` 的 instruction |
| Agent Execute 工具约束 | `agent/__init__.py` → `_EXECUTE_INSTRUCTION` |
| 能力校准 prompt | `pipeline/research.py` → `_CALIBRATE_SYSTEM` |
| 能力描述内容 | `llm/agent_client.py` 或 `agno_client.py` → `describe_capabilities()` |
| Verify 验证标准 / redecompose 判断 | `pipeline/research.py` → `_VERIFY_SYSTEM` |
| 分解逻辑 / 深度限制 | `pipeline/decompose.py` → `_SYSTEM_PROMPT_TEMPLATE` |
| Write 5 阶段 prompt | `pipeline/write.py` → `_OUTLINE/SECTION/STRUCTURE/STYLE/FORMAT_SYSTEM` |
| 全局自动化前缀 | `pipeline/research.py` → `_AUTO` |
