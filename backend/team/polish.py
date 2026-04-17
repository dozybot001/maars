"""Polish utilities: input builder and deterministic metadata appendix.

Used by WriteStage._execute() after the Writer/Reviewer loop completes.
Not a Stage subclass — polish is a phase within Write, not a separate stage.
"""

from backend.config import settings


def build_polish_input(paper: str, db) -> str:
    zh = settings.is_chinese()
    parts: list[str] = []

    if zh:
        parts.append("## 待打磨论文\n")
        parts.append(paper)
        parts.append("\n## 规范化实验摘要（事实锚点，不可篡改）\n")
    else:
        parts.append("## Paper to Polish\n")
        parts.append(paper)
        parts.append("\n## Canonical Results Summary (factual anchor — do not alter)\n")

    if db:
        summary = db.get_results_summary()
        if summary:
            parts.append(summary)

    return "\n".join(parts)


# ------------------------------------------------------------------
# Deterministic metadata appendix
# ------------------------------------------------------------------

def build_metadata_appendix(db) -> str:
    zh = settings.is_chinese()
    meta = db.get_meta() if db else {}
    research_id = db.research_id if db else "unknown"

    duration_str = _calc_duration(db)
    task_count = 0
    artifact_count = 0
    if db:
        plan_list = db.get_plan_list()
        task_count = sum(1 for t in plan_list if t.get("summary"))
        artifact_count = _count_artifacts(db)

    tokens_in = meta.get("tokens_input", 0)
    tokens_out = meta.get("tokens_output", 0)
    tokens_total = meta.get("tokens_total", 0)

    main_model = settings.google_model
    refine_model = settings.refine_model or main_model
    research_model = settings.research_model or main_model
    write_model = settings.write_model or main_model
    polish_model = settings.model_for_stage("polish")

    renderer = _render_zh if zh else _render_en
    return renderer(
        research_id=research_id, duration=duration_str,
        task_count=task_count, artifact_count=artifact_count,
        tokens_in=tokens_in, tokens_out=tokens_out, tokens_total=tokens_total,
        main_model=main_model, refine_model=refine_model,
        research_model=research_model, write_model=write_model,
        polish_model=polish_model, settings=settings,
    )


def _calc_duration(db) -> str:
    if not db:
        return "N/A"
    entries, _ = db.get_log()
    if not entries:
        return "N/A"
    first_ts = entries[0].get("ts", 0)
    last_ts = entries[-1].get("ts", 0)
    if not first_ts or not last_ts:
        return "N/A"
    return f"{(last_ts - first_ts) / 60:.1f} min"


def _count_artifacts(db) -> int:
    if not db:
        return 0
    artifacts_dir = db.get_artifacts_dir()
    if not artifacts_dir.exists():
        return 0
    return sum(1 for f in artifacts_dir.rglob("*") if f.is_file())


# ------------------------------------------------------------------
# Renderers
# ------------------------------------------------------------------

def _render_zh(*, research_id, duration, task_count, artifact_count,
               tokens_in, tokens_out, tokens_total,
               main_model, refine_model, research_model, write_model,
               polish_model, settings) -> str:
    return f"""---

## 附录：MAARS 执行报告

**Run ID** `{research_id}`

### 运行配置

| 配置项 | 值 |
|--------|-----|
| 主模型 | `{main_model}` |
| Refine 模型 | `{refine_model}` |
| Research 模型 | `{research_model}` |
| Write 模型 | `{write_model}` |
| Polish 模型 | `{polish_model}` |
| 输出语言 | `{settings.output_language}` |
| API 并发 | `{settings.api_concurrency}` |
| 研究迭代上限 | `{settings.research_max_iterations}` |
| 团队委托上限 | `{settings.team_max_delegations}` |

### 沙箱配置

| 配置项 | 值 |
|--------|-----|
| 镜像 | `{settings.docker_sandbox_image}` |
| 内存限制 | `{settings.docker_sandbox_memory}` |
| CPU 限制 | `{settings.docker_sandbox_cpu}` |
| 单次执行超时 | `{settings.docker_sandbox_timeout}s` |
| 会话超时 | `{settings.agent_session_timeout_seconds()}s` |
| 网络 | `{"启用" if settings.docker_sandbox_network else "禁用"}` |
| GPU | `{"启用" if settings.docker_sandbox_gpu else "禁用"}` |

### 运行统计

| 指标 | 值 |
|------|-----|
| 已完成任务 | `{task_count}` |
| 产物文件数 | `{artifact_count}` |
| 输入 token | `{tokens_in:,}` |
| 输出 token | `{tokens_out:,}` |
| 总 token | `{tokens_total:,}` |
| 总耗时 | `{duration}` |

### 产物清单

| 文件 | 说明 |
|------|------|
| `paper_polished.md` | 最终论文（含本附录） |
| `paper.md` | Write 阶段初稿 |
| `results_summary.json` | 规范化实验摘要 |
| `results_summary.md` | 实验摘要（可读版） |
| `plan_tree.json` | 任务分解树 |
| `meta.json` | 运行元数据 |
"""


def _render_en(*, research_id, duration, task_count, artifact_count,
               tokens_in, tokens_out, tokens_total,
               main_model, refine_model, research_model, write_model,
               polish_model, settings) -> str:
    return f"""---

## Appendix: MAARS Execution Report

**Run ID** `{research_id}`

### Configuration

| Setting | Value |
|---------|-------|
| Main model | `{main_model}` |
| Refine model | `{refine_model}` |
| Research model | `{research_model}` |
| Write model | `{write_model}` |
| Polish model | `{polish_model}` |
| Output language | `{settings.output_language}` |
| API concurrency | `{settings.api_concurrency}` |
| Research iteration limit | `{settings.research_max_iterations}` |
| Team delegation limit | `{settings.team_max_delegations}` |

### Sandbox

| Setting | Value |
|---------|-------|
| Image | `{settings.docker_sandbox_image}` |
| Memory limit | `{settings.docker_sandbox_memory}` |
| CPU limit | `{settings.docker_sandbox_cpu}` |
| Execution timeout | `{settings.docker_sandbox_timeout}s` |
| Session timeout | `{settings.agent_session_timeout_seconds()}s` |
| Network | `{"enabled" if settings.docker_sandbox_network else "disabled"}` |
| GPU | `{"enabled" if settings.docker_sandbox_gpu else "disabled"}` |

### Run Statistics

| Metric | Value |
|--------|-------|
| Completed tasks | `{task_count}` |
| Artifact files | `{artifact_count}` |
| Input tokens | `{tokens_in:,}` |
| Output tokens | `{tokens_out:,}` |
| Total tokens | `{tokens_total:,}` |
| Total duration | `{duration}` |

### File Manifest

| File | Description |
|------|-------------|
| `paper_polished.md` | Final paper (with this appendix) |
| `paper.md` | Write stage draft |
| `results_summary.json` | Canonical results summary |
| `results_summary.md` | Results summary (readable) |
| `plan_tree.json` | Task decomposition tree |
| `meta.json` | Run metadata |
"""
