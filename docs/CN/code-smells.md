# MAARS 代码坏味道清单

> 2026-03-25 全面审计，覆盖后端架构、前端、跨切面（工具/DB/SSE/配置）

## MEDIUM — 有空修

| # | 问题 | 位置 | 说明 |
|---|------|------|------|
| 11 | WriteStage phase 用字符串而非 Enum | `write.py:101` | `"outline"/"sections"/"polish"` 魔法字符串 |
| 12 | `has_broadcast` flag 是 leaky abstraction | `llm/client.py:14` | 应该在 producer 侧判断 |
| 13 | Prompt 模板散落在各 stage 文件顶部 | 多文件 | 中文指令 `_AUTO` 重复 3 次 |
| 14 | ADK 内置工具 import 失败静默吞掉 | `agent/__init__.py:18-29` | `_builtin_tools = []` 无日志 |
| 15 | 文件系统 DB 无锁 | `db.py` | Execute 并行写 + Write 并行读，TOCTOU race |
| 16 | Task dict vs dataclass 混用 | `plan.py` vs `execute.py` | 类型不一致 |
| 17 | `os.environ` side effect 在 config | `config.py:26` | Pydantic settings 偷改 env var |
| 18 | Orchestrator task key 用字符串 | `orchestrator.py:32` | 无类型约束 |
| 19 | 无日志/无可观测性 | 全局 | 无 logging，无 timing，无 `/health` |
| 20 | 前端 `window.open()` 无 null check | `process-viewer.js:164` | popup blocker 下 crash |
| 21 | CSS rgba 硬编码 | `cards.css`, `tree.css` | 应用 CSS var |
| 22 | 前端无 accessibility | `index.html` | 无 ARIA，emoji 按钮无 label |

## LOW — 知道就好

| # | 说明 |
|---|------|
| 23 | `max_rounds=999` hack（write.py） |
| 24 | MockClient `_task_counters` 不清理 |
| 25 | Research session 磁盘不清理 |
| 26 | 前端 magic number（30px、1500ms） |
| 27 | `initLogViewer()` 125 行单函数 |
| 28 | CSS `.log-separator` 定义两次 |

## 架构层面核心矛盾

1. **全局状态 vs 并发** — `_execution_log`、`_orchestrator`、`_task_counters` 都是模块级单例，假设单用户单 session
2. **Pipeline ↔ Agent 双向依赖** — pipeline 是框架层、agent 是模式层，但 `execute.py` 反向 import `agent/tools/` 破坏分层
3. **BaseStage 模板方法不够用** — Plan/Execute 都完全 override `run()`，缺少 `ParallelStage` 中间层

## 修复建议优先序

1. CRITICAL 三件套：全局状态 → FastAPI DI + per-session execution log + Queue(maxsize)
2. HIGH 代码复用：提取 `parse_json_fenced()` 到 utils、提取 `appendSeparator` 到前端 shared
3. HIGH 架构：`generate_reproduce_files` 移出 agent/tools → backend/artifacts/，解除循环依赖
4. MEDIUM 批量：Enum phase、logging、DB 公开访问器
