# 架构与数据流

## 三层架构

```
Pipeline 层（流程逻辑）
    ↓ 依赖
Interface 层（LLMClient.stream()）
    ↓ 实现
Adapter 层（Mock / Gemini / ADK Agent / Agno）
```

Pipeline 定义通用流程，Adapter 只负责 LLM 通信方式的差异。

```mermaid
flowchart TB
    subgraph Pipeline["Pipeline 层"]
        ORCH["orchestrator"] --> STAGES["refine → research → write"]
        STAGES --> DB["文件 DB"]
    end

    subgraph Interface["接口层"]
        LLM["LLMClient.stream()"]
        LLM2["LLMClient.describe_capabilities()"]
    end

    subgraph Adapters["适配层"]
        MOCK["MockClient"]
        GEMINI["GeminiClient"]
        ADK["AgentClient\n(ADK + 工具)"]
        AGNO["AgnoClient\n(Agno + 工具)"]
    end

    STAGES --> LLM
    STAGES --> LLM2
    LLM -.-> MOCK
    LLM -.-> GEMINI
    LLM -.-> ADK
    LLM -.-> AGNO

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
| **三层解耦** | `pipeline/` → `LLMClient` → `mock/gemini/agent/agno` — pipeline 不知道当前是哪个适配器 |
| **阶段间仅通过 DB 通信** | 每个阶段从 DB 读输入，写产出到 DB，不通过内存传递 |
| **读写分离** | **读**：Agent 用工具自主读取；Gemini/Mock 由 pipeline 预加载。**写**：始终由 `finalize()` 确定性写入 |
| **统一广播** | 所有 Client yield `StreamEvent`，pipeline 通过 `_dispatch_stream()` 统一广播 |
| **动态能力校准** | 原子任务定义不再硬编码——每次运行前由 LLM/Agent 自评能力边界 |
| **工具策略** | ADK 内置 > MCP 生态 > 自建（仅限内部 DB/Docker 工具） |

## 三阶段 Pipeline

```
Refine → Research → Write
```

| 阶段 | 职责 | 类 |
|------|------|-----|
| **Refine** | 将模糊想法精炼为完整研究提案 | `RefineStage` / `AgentRefineStage` |
| **Research** | 校准→分解→执行→验证→评估 循环 | `ResearchStage`（所有模式共用） |
| **Write** | 将研究产出综合为完整论文 | `WriteStage` / `AgentWriteStage` |

Research 阶段内部包含原先独立的 Plan 和 Execute 阶段的全部功能，合并后支持：
- 能力校准（Calibrate）
- 递归任务分解（Decompose）
- 拓扑排序并行执行（Execute）
- 三路验证：通过 / 重试 / 重新分解（Verify）
- 结果评估与迭代（Evaluate）

## 数据流：Gemini 模式

Pipeline 预加载所有内容到 prompt，GeminiClient 流式输出文本。

```
用户输入 idea
  ↓
REFINE（3 轮 LLM 调用）
  ├── load_input() → db.get_idea()
  ├── 3 轮：Explore → Evaluate → Crystallize
  ├── GeminiClient.stream() → yield chunks → pipeline emit → UI
  └── finalize() → db.save_refined_idea()

RESEARCH（校准 + 分解 + 执行 + 评估循环）
  ├── Phase 0: Calibrate
  │   └── LLM 自评能力边界 → 生成动态原子定义
  ├── Phase 1: Decompose
  │   └── 递归分解 → LLM 判断 atomic/decompose → plan.json
  ├── Phase 2: Execute + Verify
  │   ├── topological_batches() → 并行批次执行
  │   ├── 每个任务：execute → verify
  │   │   ├── pass=true → 保存
  │   │   ├── pass=false, redecompose=false → retry 1 次
  │   │   └── pass=false, redecompose=true → 拆分为子任务，重新编排
  │   └── db.save_task_output(id, result)
  ├── Phase 3: Evaluate（可选迭代）
  │   ├── 评估所有结果是否充分覆盖研究目标
  │   ├── satisfied → 结束
  │   └── 不满足 → 基于反馈补充分解新任务 → 回到 Phase 2
  └── _build_final_output()

WRITE（5 阶段）
  ├── Outline: 设计论文大纲，映射任务到章节
  ├── Sections: 逐章节撰写
  ├── Structure: 交叉一致性检查
  ├── Style: 学术风格润色
  ├── Format: 格式规范化
  └── finalize() → db.save_paper()
```

## 数据流：Agent 模式

Agent 通过工具自主读取输入。Refine 和 Write 使用独立的 Agent stage（单 session），
Research 复用 pipeline stage（共享逻辑，Agent 作为 LLM client）。

```
用户输入 idea
  ↓
REFINE ← AgentRefineStage（单 session）
  ├── AgentClient.stream()：
  │   ├── Agent 自主执行 Explore → Evaluate → Crystallize
  │   ├── 使用 search/fetch 工具查找真实文献
  │   └── Think/Tool/Result → broadcast → UI
  └── finalize() → db.save_refined_idea()

RESEARCH ← ResearchStage（共用，但 LLM client 是 Agent）
  ├── Phase 0: Calibrate（一次完整 Agent session）
  │   ├── Agent 知道自己有什么工具（describe_capabilities()）
  │   ├── 可试用工具探测实际可用性
  │   └── 输出：针对当前研究主题的原子任务定义
  ├── Phase 1: Decompose（使用 calibrated 定义）
  │   └── 同 Gemini 模式，但粒度适配 Agent 能力
  ├── Phase 2: Execute + Verify
  │   ├── 每个任务 → 独立 Agent session：
  │   │   ├── prompt 列出依赖 ID，Agent 用 read_task_output 工具读取
  │   │   ├── Agent 自主决策：search / code_execute / fetch
  │   │   │   └── code_execute → Docker 容器 → artifacts/ 落盘
  │   │   └── verify → pass / retry / redecompose
  │   └── 重新分解的子任务继承父任务 partial output 作为 context
  └── _build_final_output() + generate_reproduce_files()

WRITE ← AgentWriteStage（单 session）
  ├── AgentClient.stream()：
  │   ├── Agent 调用 list_tasks → read_task_output → read_refined_idea
  │   ├── Agent 自主决定论文结构并撰写
  │   └── 完整论文 → yield → pipeline
  └── finalize() → db.save_paper()
```

## 模式对比

| | Gemini/Mock | ADK Agent | Agno |
|---|---|---|---|
| Refine | RefineStage（3 轮 LLM） | AgentRefineStage（1 session） | AgentRefineStage（1 session） |
| Research | ResearchStage（并行 LLM 调用） | ResearchStage（并行 Agent session） | ResearchStage（并行 Agent session） |
| Write | WriteStage（5 phase 多轮） | AgentWriteStage（1 session） | AgentWriteStage（1 session） |
| 原子校准 | 文本 LLM 自评 | Agent session（带工具） | Agent session（带工具） |
| 依赖注入 | 内容塞进 prompt | Agent 调 `read_task_output` | Agent 调 `read_task_output` |
| 工具 | 无 | google_search, url_context, code_execute, Fetch MCP | DuckDuckGo, arXiv, Wikipedia |
| 代码执行 | 无 | Docker sandbox | Docker sandbox |
| 文件产出 | 仅 paper.md | paper.md + artifacts/ + Docker 复现文件 | paper.md + artifacts/ + Docker 复现文件 |

## 阶段间通信

阶段之间**仅通过 DB** 通信。

```
results/{timestamp-slug}/
├── idea.md              Refine 读取
├── refined_idea.md      Research 读取    ← Refine 写入
├── plan.json            Research 内部    ← Research.decompose 写入
├── plan_tree.json       前端/Write       ← Research.decompose 写入
├── tasks/*.md           Write 读取      ← Research.execute 写入
├── artifacts/           Write 引用      ← Docker 写入（Agent 模式）
├── evaluations/*.json   Research 内部    ← Research.evaluate 写入
└── paper.md                            ← Write 写入
```

## 阶段控制：Stop / Resume / Retry

| 操作 | 行为 |
|------|------|
| **Stop** | 取消 asyncio task，状态 → PAUSED。Agent ReAct loop 被 break |
| **Resume** | 重启 `run()`。Research 从 DB checkpoint 恢复（`tasks/*.md` 存在 = 已完成），跳过已完成任务。其他 stage 等同于 retry |
| **Retry** | 清空状态 + DB 文件，完全从头重跑。同时重置所有下游 stage |

```
Stop:
  orchestrator.stop_stage()
    → llm_client.request_stop()
    → stage._run_id += 1    // stale check 失效
    → cancel_task()          // CancelledError 传播
    → state = PAUSED

Resume（Research）:
  orchestrator.resume_stage()
    → stage.run()
      → _load_checkpoint()   // DB 读取已完成 task
      → 跳过 _task_results 中已有的 task
      → 执行剩余 task
```

## 文件结构

```
backend/
├── main.py                          # FastAPI 入口
├── config.py                        # 配置（环境变量）
├── db.py                            # ResearchDB：文件存储
├── utils.py                         # JSON 解析工具
├── reproduce.py                     # Docker 复现文件生成
│
├── pipeline/                        # 流程层（模式无关）
│   ├── stage.py                     # BaseStage 基类
│   ├── refine.py                    # RefineStage
│   ├── research.py                  # ResearchStage（含 calibrate/decompose/execute/evaluate）
│   ├── decompose.py                 # 递归任务分解
│   ├── evaluate.py                  # 结果评估
│   ├── write.py                     # WriteStage（5 phase）
│   └── orchestrator.py              # 编排器：阶段调度 + SSE 广播
│
├── llm/                             # 接口层
│   ├── client.py                    # LLMClient 抽象基类 + StreamEvent
│   ├── gemini_client.py             # Gemini API
│   ├── agent_client.py              # ADK Agent → StreamEvent
│   └── agno_client.py               # Agno Agent → StreamEvent
│
├── gemini/                          # Gemini 模式工厂
├── mock/                            # Mock 模式工厂 + 测试数据
├── agent/                           # ADK 模式工厂 + 工具
│   ├── __init__.py                  # create_agent_stages()
│   ├── stages.py                    # AgentRefineStage, AgentWriteStage
│   └── tools/shared/               # DB 工具、Docker 工具
└── agno/                            # Agno 模式工厂
    ├── __init__.py                  # create_agno_stages()
    └── models.py                    # 多 provider 模型创建
```

## 工具策略

```
ADK 模式：ADK 内置（google_search, url_context）+ MCP（Fetch）+ 自建（DB、Docker）
Agno 模式：Agno 内置（DuckDuckGo、arXiv、Wikipedia）+ 自建（DB、Docker）
代码执行统一走 Docker sandbox（隔离容器，限制资源，无网络）
```

不设 Skill 层 — 模型原生 ReAct 推理替代显式编排。
