# Agent 目录结构规范

Idea、Plan、Task 三个 Agent 保持统一目录结构，便于维护与扩展。

## 统一结构

```
{agent}/
├── agent.py           # Agent 入口，*AgentMode=True 时调用
├── adk_runner.py      # Google ADK 驱动实现（仅 Agent 模式）
├── agent_tools.py     # 工具定义 + execute 逻辑
├── llm/               # 单轮 LLM 实现（Mock/LLM 模式）
│   ├── __init__.py
│   └── executor.py    # 各阶段 LLM 调用
├── prompts/           # Prompt 文件
│   ├── {agent}-agent-prompt.txt   # Agent 模式 system prompt
│   └── reflect-prompt.txt         # Self-Reflection 评估 prompt
├── skills/            # Agent Skills（SKILL.md + references/scripts 等）
│   └── {skill-name}/
│       └── SKILL.md   # YAML frontmatter + Markdown 内容
└── __init__.py
```

## 各 Agent 差异

| 组件 | Idea | Plan | Task |
|------|------|------|------|
| 编排 | 无（API 直接调用） | `index.py` | `runner.py` |
| 领域模块 | `arxiv.py` | `execution_builder.py` | `artifact_resolver.py`, `pools.py`, `web_tools.py` |
| LLM 子模块 | `llm/executor.py` | `llm/executor.py` | `llm/executor.py`, `llm/validation.py` |

## Skills 规范

- **位置**：`{agent}/skills/{skill-name}/`
- **入口**：`SKILL.md`，含 YAML frontmatter（`name`, `description`）
- **发现**：`shared/skill_utils.list_skills(skills_root)` 扫描目录
- **加载**：`shared/skill_utils.load_skill(skills_root, name)` 读取 SKILL.md

Task Agent 的 Skills 可含 `scripts/`、`references/`；Idea/Plan 以 SKILL.md 为主。

## 解耦要点

1. **Skill I/O**：统一由 `shared/skill_utils` 提供，各 agent_tools 仅传入 `*_SKILLS_ROOT`
2. **ADK 桥接**：工具格式转换、ExecutorTool 封装由 `shared/adk_bridge` 统一处理
3. **ADK 运行时**：Runner 生命周期、事件循环、中止控制由 `shared/adk_runtime` 统一处理，减少三个 `adk_runner.py` 重复逻辑
4. **Realtime 事件**：thinking 事件 payload 组装由 `shared/realtime` 统一处理，减少路由重复代码
5. **LLM 调用**：单轮调用由 `shared/llm_client.chat_completion` 统一；Mock 由 `test/mock_stream.mock_chat_completion` 统一

## 会话运行时

- `api/state.py` 维护 `sessionId -> SessionState` 映射，每个会话独立持有：
  - Task `ExecutionRunner`
  - Plan / Idea / Paper 的 run_state（abort_event、run_task）
- 由 `POST /api/session/init` 签发 `sessionId + sessionToken`
- 前端通过 `X-MAARS-SESSION-ID + X-MAARS-SESSION-TOKEN`（HTTP）+ `auth.sessionId + auth.sessionToken`（WebSocket）绑定同一会话
- 所有事件按 session room 定向发射，避免多用户串流
- 空闲会话按 TTL 回收，降低长期内存占用
