# MAARS CLI 命令参考

> 完整的命令清单、参数详解、示例和常见问题。快速概览见 [README.md](../README.md#使用)。

## 总览

| 命令 | 类别 | 用途 |
|---|---|---|
| `maars refine` | **graph** | Refine graph（Explorer ↔ Critic 对抗循环） |
| `maars hello` | diagnostic | CLI wiring smoke test |
| `maars sanity` | debug | 单次 chat model invoke，验证 API + key |
| `maars draft` | debug | 单次 Explorer 调用，不迭代 |
| `maars critique` | debug | 单次 Critic 调用，不迭代 |

**快速启动**：

```bash
uv run maars --help            # 看所有命令
uv run maars refine --help     # 看某个命令的完整参数
```

> **注意**：M2 Write graph 实现**暂停**（见 [roadmap.md](roadmap.md#m2--write-graph-可跑独立--paused)），项目先聚焦 M1 Refine 的打磨和实际测试。

---

## Graph 命令

### `maars refine`

运行完整的 Refine graph——Explorer 起草研究提案，Critic 审查，迭代直到 `passed=True` 或达到 `MAARS_REFINE_MAX_ROUND`。

**每次调用默认新开一个 thread**，自动分配 `refine-NNN` 编号，不再有"default thread resume"冲突。只有显式传 `--thread <id>` 才进入 resume 语义。

#### Synopsis

```
uv run maars refine [RAW_IDEA] [OPTIONS]
uv run maars refine --from-file <PATH> [OPTIONS]
```

#### 参数

| 参数 | 类型 | 必需 | 默认 | 说明 |
|---|---|---|---|---|
| `RAW_IDEA` | positional | 二选一 | `""` | 研究想法字符串 |
| `--from-file`, `-f` | Path | 二选一 | — | 从 markdown 文件读取 idea（推荐长 idea 或含特殊字符） |
| `--thread` | str | 否 | **auto（新编号）** | 显式指定 thread id 用于 resume。**省略则自动分配新的 `refine-NNN`** |

#### 示例

```bash
# 最简：新开一次 refine，自动分配编号（第一次是 refine-001）
uv run maars refine "研究大模型推理"

# 长 idea 从文件读
uv run maars refine --from-file examples/test_ideas/speculative_decoding.md

# Resume 一个中断的 thread（thread id 从上次的输出最后一行复制）
uv run maars refine --thread refine-003

# 连续跑多个 idea 对比（每次自动拿到新编号）
uv run maars refine "idea A"    # → refine-004
uv run maars refine "idea B"    # → refine-005
uv run maars refine "idea C"    # → refine-006
```

#### 输出

**Streaming events**（实时）：

```
Starting thread refine-001
────────────────────────────────
-> explorer running...
ok explorer round 1 — draft generated (2047 chars)
-> critic running...
ok critic — 5 issues, passed=False
-> explorer running...
ok explorer round 2 — draft generated (2340 chars)
ok critic — 3 issues, passed=False, resolved+5
...
```

**Final Rich Panel**：完整的 refined draft（不截断）

**Remaining issues**：按 severity 分色（red blocker / yellow major / dim minor）

**Session 落盘**：每次 run 创建一个独立的 session 目录 `data/refine/{NNN}/`。

---

## Session 文件组织

每次 `maars refine` 调用创建一个独立的 session 目录：

```
data/
├── checkpoints.db                  # LangGraph SQLite，所有 thread 的运行时 state
└── refine/
    ├── 001/
    │   ├── raw_idea.md             # 用户的原始输入
    │   ├── draft.md                # 最终的 refined draft
    │   ├── issues.json             # 剩余未解决 issues（结构化 JSON）
    │   └── meta.json               # 运行元数据
    ├── 002/
    ├── 003/
    └── ...
```

### `meta.json` 示例

```json
{
  "thread_id": "refine-001",
  "finished_at": "2026-04-12T02:34:22+00:00",
  "model": "gemini-3-flash-preview",
  "max_round": 5,
  "final_round": 5,
  "passed": false,
  "total_resolved": 15,
  "remaining_issues": {
    "blocker": 0,
    "major": 2,
    "minor": 1
  }
}
```

### 为什么这样组织

- **每次 run 的所有产物在一起**——不用在多个目录里翻找
- **数字编号清晰**，`ls data/refine/` 按顺序看所有历史
- **`meta.json` 可脚本化分析**——哪些 passed / 哪些 stuck / 哪些 idea 最难，都能从元数据里统计
- **Raw idea 保留**，能看到每次 refine 是从什么输入开始的
- **Issues 是 JSON 而不是 Markdown**——future 可以做"批量找所有剩 blocker 的 session"这种 query

---

## Debug / Diagnostic 命令

这些命令主要用于开发调试，**不是正常使用流程的一部分**。

### `maars hello`

最轻量的 CLI 自检。不打 API，0 花费。

```bash
uv run maars hello
# MAARS CLI ready.
```

### `maars sanity`

单次 chat model 调用，验证 `GOOGLE_API_KEY` + 模型 ID 正常。**遇到 API / 配置问题第一步就跑这个**。

```bash
uv run maars sanity
# Model: gemini-3-flash-preview
# Response: hello from model
```

打 1 次 API，< $0.001。

### `maars draft <raw_idea>`

只跑一次 Explorer，不进入 Refine 循环。用于快速看 Explorer 的 output 样子。

```bash
uv run maars draft "研究大模型推理"
```

打 1 次 Gemini API + grounding，约 10-20 秒，< $0.01。

### `maars critique <draft>`

只跑一次 Critic，不进入循环。对一个 draft 字符串给出**增量反馈**（`new_issues` + `resolved` + `summary`，不含 `passed` 因为 standalone 模式下没有 prior 对比）。

```bash
uv run maars critique "我想在 GSM8K 上研究 CoT 效果"
```

打 1 次 Gemini API，约 5-10 秒，< $0.005。

---

## 环境变量

所有配置通过 env 变量调整，**不通过命令行参数**。长期配置写进 `.env`。

| 变量 | 默认 | 说明 |
|---|---|---|
| `GOOGLE_API_KEY` | — | **必填**，Gemini API key |
| `MAARS_CHAT_MODEL` | `gemini-3-flash-preview` | Gemini 模型 ID |
| `MAARS_REFINE_MAX_ROUND` | `5` | Refine 最大迭代轮次 |

### `.env` 示例

```bash
GOOGLE_API_KEY=sk-your-key-here
MAARS_CHAT_MODEL=gemini-3-flash-preview
MAARS_REFINE_MAX_ROUND=8
```

### 想让 Refine 更容易收敛到 `passed=True`？

改 `.env` 里的 `MAARS_REFINE_MAX_ROUND`。默认 5 对复杂 idea 可能不够，调到 `8` 或 `10` 让 Critic 有更多轮空间。

---

## 文件位置约定

| 路径 | 内容 | git 跟踪 |
|---|---|---|
| `data/checkpoints.db` | LangGraph 所有 thread 的运行时 state | ❌ |
| `data/refine/{NNN}/raw_idea.md` | 原始输入 | ❌ |
| `data/refine/{NNN}/draft.md` | 最终 refined draft | ❌ |
| `data/refine/{NNN}/issues.json` | 剩余 issues 结构化 | ❌ |
| `data/refine/{NNN}/meta.json` | 运行元数据 | ❌ |
| `examples/test_ideas/` | 自带的测试 idea（可做测试 fixture） | ✅ |

---

## FAQ

**Q: 我的 thread 编号会不会重置？**

A: 不会。`_next_thread_id()` 扫描 `data/refine/` 下已有的编号取最大值 + 1。即使你删掉中间编号（比如只留 001 和 003），下一次仍然是 004。

**Q: 怎么 resume 一个中断的 refine？**

A: 上次 run 的最后一行会打印 `Resume: uv run maars refine --thread refine-NNN`，直接复制即可。或者 `ls data/refine/` 看编号自己拼。

**Q: `passed=False` 到 MAX_ROUND 是 bug 吗？**

A: 不是。Critic 严格，每轮都能找到更深的 issue。想让它更容易 pass，在 `.env` 里调 `MAARS_REFINE_MAX_ROUND=8` 或更大。

**Q: 怎么清空所有 refine 历史？**

A:

```bash
rm -rf data/refine/ data/checkpoints.db
```

下次 run 又从 `refine-001` 开始。

**Q: 我的 idea 用英文写可以吗？**

A: 可以。prompt 是中文的（Explorer/Critic 角色），但 idea 内容不限。Gemini 双语都行。

**Q: 一次 Refine 大概多少 API 花费？**

A: 每轮 Explorer + Critic ≈ $0.005-0.007。5 轮（默认 MAX）总共约 $0.03-0.04 一次完整 Refine。

---

## 调试 checklist

遇到问题按顺序排查：

1. `uv run maars hello` — CLI 能启动吗？
2. `uv run maars sanity` — API key 和模型正常吗？
3. `ls data/refine/` — 现有 session 长什么样？
4. `uv run maars refine --help` — 参数签名和你的命令对得上吗？
5. 看 traceback — 错在 Python / Pydantic / LangGraph / Gemini API 哪一层？

---

## 相关文档

- [README.md](../README.md) — 项目概览
- [docs/concept.md](concept.md) — 核心思想
- [docs/architecture.md](architecture.md) — 技术栈和模块设计
- [docs/graph.md](graph.md) — Graph / State / Node / Edge 定义
- [docs/roadmap.md](roadmap.md) — 里程碑
