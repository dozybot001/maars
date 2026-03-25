# 架构与数据流

## 三层架构

```
Pipeline 层（流程逻辑）
    ↓ 依赖
Interface 层（LLMClient.stream()）
    ↓ 实现
Adapter 层（Mock / Gemini / Agent）
```

Pipeline 定义通用流程，Adapter 只负责 LLM 通信方式的差异。

```mermaid
flowchart TB
    subgraph Pipeline["Pipeline 层"]
        ORCH["orchestrator"] --> STAGES["refine → plan → execute → write"]
        STAGES --> DB["文件 DB"]
    end

    subgraph Interface["接口层"]
        LLM["LLMClient.stream()"]
    end

    subgraph Adapters["适配层"]
        MOCK["MockClient"]
        GEMINI["GeminiClient"]
        AGENT["AgentClient\n(ADK + 工具)"]
    end

    STAGES --> LLM
    LLM -.-> MOCK
    LLM -.-> GEMINI
    LLM -.-> AGENT

    subgraph FE["前端"]
        UI["输入 + 控制"]
        LOG["推理日志"]
        PROC["流程 & 产出"]
    end

    UI --> ORCH
    ORCH -."SSE".-> LOG
    ORCH -."SSE".-> PROC
```

## 设计原则

| 原则 | 说明 |
|------|------|
| **三层解耦** | `pipeline/` → `LLMClient` → `mock/gemini/agent` — pipeline 不知道当前是哪个适配器 |
| **阶段间仅通过 DB 通信** | 每个阶段从 DB 读输入，写产出到 DB，不通过内存传递字符串 |
| **读写分离** | **读**：Agent 用工具自主读取；Gemini/Mock 由 pipeline 预加载。**写**：始终由 `finalize()` 确定性写入 |
| **广播分离** | `has_broadcast=False`（Gemini/Mock）：pipeline 发送 chunk。`has_broadcast=True`（Agent）：适配器广播 Think/Tool/Result |
| **工具策略** | ADK 内置 > MCP 生态 > 自建（仅限内部 DB 工具） |

## 数据流：Gemini 模式

Pipeline 预加载所有内容到 prompt，GeminiClient 流式输出文本。

```
用户输入 idea
  ↓
REFINE
  ├── load_input() → db.get_idea()         [pipeline 预加载]
  ├── 3 轮：Explore → Evaluate → Crystallize
  ├── GeminiClient.stream() → yield chunks → pipeline emit → UI
  └── finalize() → db.save_refined_idea()

PLAN
  ├── load_input() → db.get_refined_idea()  [pipeline 预加载]
  ├── 递归分解 → LLM 判断 atomic/decompose
  └── _finalize_output() → db.save_plan(json, tree)

EXECUTE
  ├── load_input() → db.get_plan_json()     [pipeline 预加载]
  ├── topological_batches() → 并行批次执行
  ├── 每个任务：
  │   ├── 依赖内容从 DB 预加载到 prompt
  │   ├── exec → verify → 失败则 retry
  │   └── db.save_task_output(id, result)
  └── _build_final_output()

WRITE
  ├── load_input() → ""                     [build_messages 内部读 DB]
  ├── outline: db.get_refined_idea() + 任务列表
  ├── sections: db.get_task_output(tid) 按章节读取
  ├── polish: 组装全文润色
  └── finalize() → db.save_paper()
```

## 数据流：Agent 模式

Agent 通过工具自主读取输入，Pipeline 只提供指令。

```
用户输入 idea
  ↓
REFINE
  ├── load_input() → db.get_idea()          [内容短，直接传]
  ├── AgentClient.stream()：
  │   ├── Agent 使用 search/arXiv/fetch 工具
  │   ├── Think/Tool/Result → broadcast → UI
  │   └── 最终结论 → yield → pipeline
  ├── 3 轮：Explore → Evaluate → Crystallize
  └── finalize() → db.save_refined_idea()

PLAN
  ├── load_input() → db.get_refined_idea()  [无工具，直接从 DB 读，同 Gemini]
  ├── AgentClient(tools=[]) → 退化为普通 LLM 调用
  ├── 递归分解（同 Gemini 模式）
  └── _finalize_output() → db.save_plan(json, tree)

EXECUTE
  ├── load_input() → db.get_plan_json()     [结构化数据，pipeline 直接读]
  ├── topological_batches() → 并行批次执行
  ├── 每个任务：
  │   ├── prompt 列出依赖 ID，Agent 用 read_task_output 工具读取
  │   ├── Agent 自主决策：search / code_execute / fetch
  │   │   └── code_execute → Docker 容器 → artifacts/ 落盘
  │   ├── verify → 失败则 retry → 再失败则阶段停止
  │   └── db.save_task_output(id, result)
  └── _build_final_output()

WRITE
  ├── load_input() → "Use list_tasks and read_task_output tools..."
  ├── AgentClient.stream()：
  │   ├── Agent 调用 list_tasks → read_task_output → read_refined_idea
  │   ├── Agent 搜索 arXiv 补充引用
  │   └── 完整论文 → yield → pipeline
  └── finalize() → db.save_paper()
```

## 模式对比

| | Gemini | Agent |
|---|---|---|
| 读输入 | Pipeline 从 DB 预加载 | Refine/Plan：DB 预加载（同 Gemini）；Execute/Write：Agent 用工具读取 |
| 写输出 | `finalize()` 确定性写 DB | 同左 |
| 依赖注入 | 内容塞进 prompt | 列出 ID，Agent 调 `read_task_output` |
| 工具 | 无 | 搜索、代码执行、DB、网页抓取 |
| UI 广播 | Pipeline emit chunks | AgentClient broadcast |
| 文件产出 | 无 artifacts | `artifacts/`（Docker 落盘） |

## 阶段间通信

阶段之间**仅通过 DB** 通信，不传递内存字符串。

```
research/{id}/
├── idea.md              Refine 读取
├── refined_idea.md      Plan 读取      ← Refine 写入
├── plan.json            Execute 读取   ← Plan 写入
├── plan_tree.json       (UI + Write)   ← Plan 写入
├── tasks/*.md           Write 读取     ← Execute 写入
├── artifacts/           Write 引用     ← Execute/Docker 写入
├── paper.md                            ← Write 写入
└── reasoning.log                       ← 前端保存
```

## 工具策略

```
优先级：
1. ADK 内置（google_search, url_context, BuiltInCodeExecutor）
2. MCP 生态（arXiv MCP, Fetch MCP）
3. 自建（DB 工具、Docker 工具 — 仅限内部数据访问）
```

不设 Skill 层 — 模型原生 ReAct 推理替代显式 Skill 编排。
