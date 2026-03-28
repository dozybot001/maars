# MAARS 代码坏味道清单

> 2026-03-28 更新，同步三阶段架构重构

## MEDIUM — 有空修

| # | 问题 | 位置 | 说明 |
|---|------|------|------|
| 11 | WriteStage phase 用字符串而非 Enum | `write.py:189` | `"outline"/"sections"/"structure"/"style"/"format"` 魔法字符串 |
| 13 | Prompt 模板散落在各 stage 文件顶部 | `research.py`, `refine.py`, `write.py` | `_AUTO` 前缀重复定义 |
| 14 | ADK 内置工具 import 失败静默吞掉 | `agent/__init__.py:16-20` | `_builtin_tools = []` 无日志 |
| 15 | 文件系统 DB 无锁 | `db.py` | Research 并行写 + Write 读，TOCTOU race |
| 17 | `os.environ` side effect 在 config | `config.py:36-40` | `os.environ.setdefault()` 偷改环境变量 |
| 18 | Orchestrator task key 用字符串 | `orchestrator.py` | `_tasks["pipeline"]` 无类型约束 |
| 19 | 无日志/无可观测性 | 全局 | 无 logging，无 timing，无 `/health` |
| 20 | 前端 `window.open()` 无 null check | `process-viewer.js:140` | popup blocker 下 crash |
| 21 | CSS rgba 硬编码 | `cards.css`, `tree.css` | 应用 CSS var |
| 22 | 前端无 accessibility | `index.html` | 无 ARIA，emoji 按钮无 label |

## LOW — 知道就好

| # | 说明 |
|---|------|
| 23 | `max_rounds=999` hack（`write.py:186`）— WriteStage 用超大 round 数绕过 BaseStage 循环限制 |
| 24 | MockClient `_task_counters` 不清理（`mock/client.py`） |
| 25 | Research session 磁盘不清理 — `results/` 只增不删 |
| 26 | 前端 magic number（30px、1500ms 等） |
| 28 | CSS `.log-separator` 在 `workspace.css` 中定义两次（行 87 和 144） |

## 架构层面

| # | 问题 | 说明 |
|---|------|------|
| A1 | **全局状态 vs 并发** | `main.py` 中 `orchestrator` 是模块级单例，假设单用户单 session。应改为 FastAPI DI + per-session |
| A2 | **BaseStage 模板方法覆盖面不足** | `ResearchStage` 完全 override `run()`，BaseStage 的 multi-round 模板对它无用。可考虑分离 `IterativeStage` 基类 |

## 已修复（本次重构）

| 原 # | 问题 | 修复方式 |
|------|------|---------|
| 12 | `has_broadcast` leaky abstraction | 已删除，Client 不再持有 broadcast 引用 |
| 16 | Task dict vs dataclass 混用 | `decompose.py` 内部用 `Task` dataclass，对外统一输出 `dict`，接口清晰 |
| A2(旧) | Pipeline ↔ Agent 双向依赖 | `generate_reproduce_files` 已移至 `reproduce.py`，pipeline 层调用，不反向依赖 agent 层 |
| A3(旧) | Plan/Execute 都 override run() | 合并为 `ResearchStage`，一个类一次 override |

## 修复建议优先序

1. **HIGH**: 全局状态 → FastAPI DI + per-session orchestrator
2. **HIGH**: 日志/可观测性 → 接入 Python logging + `/health` endpoint
3. **MEDIUM**: WriteStage phase Enum 化 + `_AUTO` 提取到 `pipeline/prompts.py`
4. **MEDIUM**: DB 加文件锁 / 改用 SQLite
