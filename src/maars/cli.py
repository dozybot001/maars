"""CLI entry point."""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import typer

app = typer.Typer(help="MAARS — Multi-Agent Automated Research System")


@app.callback()
def _root() -> None:
    """MAARS — Multi-Agent Automated Research System."""


@app.command()
def hello() -> None:
    """Sanity check: prove the CLI wiring is alive."""
    typer.echo("MAARS CLI ready.")


@app.command()
def sanity() -> None:
    """(debug) Smoke-test the chat model by invoking it once."""
    from maars.config import CHAT_MODEL
    from maars.models import get_chat_model

    typer.echo(f"Model: {CHAT_MODEL}")
    model = get_chat_model()
    response = model.invoke("Reply with exactly three words: hello from model")
    content = response.content
    if isinstance(content, list):
        text = "".join(
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    else:
        text = str(content)
    typer.echo(f"Response: {text}")


@app.command()
def critique(
    draft: str = typer.Argument(..., help="The research proposal draft to critique"),
) -> None:
    """(debug) Run the Critic on a draft once and print incremental feedback."""
    from maars.agents.critic import critique_draft

    result = critique_draft(draft)

    typer.echo(f"Summary: {result.summary}")
    typer.echo("")
    typer.echo(f"New issues ({len(result.new_issues)}):")
    for issue in result.new_issues:
        typer.echo(f"  [{issue.id}] ({issue.severity}) {issue.summary}")
        typer.echo(f"    -> {issue.detail}")
    if result.resolved:
        typer.echo("")
        typer.echo(f"Resolved from prior: {', '.join(result.resolved)}")


@app.command()
def draft(
    raw_idea: str = typer.Argument(..., help="The raw research idea to expand into a draft"),
) -> None:
    """(debug) Run the Explorer on a raw idea once and print the draft proposal."""
    from maars.agents.explorer import draft_proposal

    result = draft_proposal(raw_idea)
    typer.echo(result)


def _next_thread_id() -> str:
    """Generate the next auto-incrementing thread id, e.g. 'refine-001'."""
    from maars.config import DATA_DIR

    refine_dir = DATA_DIR / "refine"
    refine_dir.mkdir(parents=True, exist_ok=True)

    existing_nums: list[int] = []
    for p in refine_dir.iterdir():
        if p.is_dir() and p.name.isdigit():
            existing_nums.append(int(p.name))

    next_num = max(existing_nums, default=0) + 1
    return f"refine-{next_num:03d}"


def _session_dir_for(thread_id: str) -> Path:
    """Resolve the data/refine/ subdirectory for a given thread id.

    Strips only the 'refine-' prefix when present (so auto 'refine-001'
    maps to data/refine/001/), otherwise uses the id verbatim (so a
    custom 'exp1' or 'verify-stream' maps to data/refine/exp1/ or
    data/refine/verify-stream/).
    """
    from maars.config import DATA_DIR

    if thread_id.startswith("refine-"):
        sub = thread_id[len("refine-"):]
    else:
        sub = thread_id
    return DATA_DIR / "refine" / sub


def _empty_usage_bucket() -> dict[str, int]:
    return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}


def _accumulate_usage(
    bucket: dict[str, int],
    usage_meta: dict | None,
) -> None:
    """Add LangChain usage_metadata tokens into a running bucket."""
    if not usage_meta:
        return
    bucket["input_tokens"] += int(usage_meta.get("input_tokens") or 0)
    bucket["output_tokens"] += int(usage_meta.get("output_tokens") or 0)
    bucket["total_tokens"] += int(usage_meta.get("total_tokens") or 0)


def _extract_usage_metadata(data: dict) -> dict | None:
    """Pull usage_metadata out of an on_chat_model_end event's data.output.

    LangChain 1.x puts the AIMessage under data['output']. Older shapes
    may wrap it in a generation/message. We probe both to be safe.
    """
    output_obj = data.get("output")
    if output_obj is None:
        return None
    usage = getattr(output_obj, "usage_metadata", None)
    if usage:
        return usage
    message = getattr(output_obj, "message", None)
    if message is not None:
        usage = getattr(message, "usage_metadata", None)
        if usage:
            return usage
    if isinstance(output_obj, dict):
        return output_obj.get("usage_metadata")
    return None


def _esc_listener_supported() -> bool:
    """Whether the current environment supports the ESC-key listener."""
    if sys.platform == "win32":
        return False
    try:
        return sys.stdin.isatty()
    except Exception:
        return False


async def _listen_for_esc(cancel_event: asyncio.Event) -> None:
    """Listen for ESC key on stdin and set cancel_event on press.

    Uses termios/tty to put stdin in cbreak mode and asyncio.add_reader
    for non-blocking reads. Unix-only. On Windows, or when stdin is not
    a TTY (e.g. piped input under a subprocess runner), it is a no-op
    and Ctrl-C remains the only interrupt mechanism.
    """
    if not _esc_listener_supported():
        # Park forever until the caller cancels us.
        await cancel_event.wait()
        return

    import termios
    import tty

    loop = asyncio.get_running_loop()
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    def _on_stdin() -> None:
        try:
            ch = sys.stdin.read(1)
        except Exception:
            return
        if ch == "\x1b":  # ESC
            cancel_event.set()

    try:
        tty.setcbreak(fd)
        loop.add_reader(fd, _on_stdin)
        await cancel_event.wait()
    finally:
        try:
            loop.remove_reader(fd)
        except Exception:
            pass
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except Exception:
            pass


def _save_refine_session(
    thread_id: str,
    raw_idea: str,
    values: dict,
    *,
    started_at: datetime,
    finished_at: datetime,
    usage_by_node: dict[str, dict[str, int]],
    interrupted: bool,
) -> Path:
    """Save final session artifacts under data/refine/{sub}/.

    Writes:
        data/refine/{sub}/raw_idea.md   -- the original input
        data/refine/{sub}/draft.md      -- the final refined draft
        data/refine/{sub}/issues.json   -- remaining unresolved issues
        data/refine/{sub}/meta.json     -- run metadata (timing + usage + interrupted flag)
    """
    from maars.config import CHAT_MODEL, REFINE_MAX_ROUND

    session_dir = _session_dir_for(thread_id)
    session_dir.mkdir(parents=True, exist_ok=True)

    (session_dir / "raw_idea.md").write_text(raw_idea, encoding="utf-8")

    draft_text = values.get("draft", "") or ""
    (session_dir / "draft.md").write_text(draft_text, encoding="utf-8")

    issues = values.get("issues") or []
    issues_data = [
        i.model_dump() if hasattr(i, "model_dump") else dict(i) for i in issues
    ]
    (session_dir / "issues.json").write_text(
        json.dumps(issues_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    blockers = sum(1 for i in issues if i.severity == "blocker")
    majors = sum(1 for i in issues if i.severity == "major")
    minors = sum(1 for i in issues if i.severity == "minor")

    total_usage = _empty_usage_bucket()
    for node_usage in usage_by_node.values():
        total_usage["input_tokens"] += node_usage["input_tokens"]
        total_usage["output_tokens"] += node_usage["output_tokens"]
        total_usage["total_tokens"] += node_usage["total_tokens"]

    duration_seconds = round((finished_at - started_at).total_seconds(), 3)

    meta = {
        "thread_id": thread_id,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": duration_seconds,
        "model": CHAT_MODEL,
        "max_round": REFINE_MAX_ROUND,
        "final_round": values.get("round", 0),
        "passed": values.get("passed", False),
        "interrupted": interrupted,
        "total_resolved": len(values.get("resolved") or []),
        "remaining_issues": {
            "blocker": blockers,
            "major": majors,
            "minor": minors,
        },
        "usage": {
            "total_tokens": total_usage["total_tokens"],
            "input_tokens": total_usage["input_tokens"],
            "output_tokens": total_usage["output_tokens"],
            "by_node": usage_by_node,
        },
    }
    (session_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return session_dir


@app.command()
def refine(
    raw_idea: str = typer.Argument(
        "", help="The raw research idea to refine (or use --from-file)"
    ),
    thread_id: str = typer.Option(
        None,
        "--thread",
        help="Thread ID for resume. Omit to auto-generate a new 'refine-NNN' thread.",
    ),
    from_file: Path = typer.Option(
        None,
        "--from-file",
        "-f",
        help="Read raw idea from a markdown file",
    ),
) -> None:
    """Run the full Refine graph with streaming events and checkpoint-based resume."""
    if from_file is not None:
        if not from_file.exists():
            typer.echo(f"Error: file not found: {from_file}", err=True)
            raise typer.Exit(1)
        raw_idea = from_file.read_text(encoding="utf-8")

    if not raw_idea.strip():
        typer.echo(
            "Error: provide a raw idea (positional argument or --from-file)", err=True
        )
        raise typer.Exit(1)

    if thread_id is None:
        thread_id = _next_thread_id()

    asyncio.run(_refine_async(raw_idea, thread_id))


async def _refine_async(raw_idea: str, thread_id: str) -> None:
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule

    from maars.config import CHECKPOINT_DB
    from maars.graphs.refine import build_refine_graph

    console = Console()
    CHECKPOINT_DB.parent.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(timezone.utc)
    usage_by_node: dict[str, dict[str, int]] = {
        "explorer": _empty_usage_bucket(),
        "critic": _empty_usage_bucket(),
    }

    serde = JsonPlusSerializer(
        allowed_msgpack_modules=[("maars.state", "Issue")]
    )

    async with AsyncSqliteSaver.from_conn_string(str(CHECKPOINT_DB)) as checkpointer:
        checkpointer.serde = serde
        graph = build_refine_graph(checkpointer)

        config: dict = {"configurable": {"thread_id": thread_id}}
        existing = await graph.aget_state(config)
        has_state = bool(existing and existing.values)

        if has_state:
            cur_round = existing.values.get("round", 0)
            console.print(
                f"[yellow]Resuming thread [bold]{thread_id}[/bold] from round {cur_round}[/yellow]"
            )
            input_state = None
        else:
            console.print(f"[cyan]Starting thread [bold]{thread_id}[/bold][/cyan]")
            input_state = {"raw_idea": raw_idea, "round": 0}

        console.print(Rule(style="dim"))
        if _esc_listener_supported():
            console.print("[dim](press ESC or Ctrl-C to interrupt; partial state will be saved)[/dim]")
            console.print()

        cancel_event = asyncio.Event()
        esc_task = asyncio.create_task(_listen_for_esc(cancel_event))
        interrupted = False
        current_status = None

        try:
            async for event in graph.astream_events(input_state, config=config, version="v2"):
                if cancel_event.is_set():
                    interrupted = True
                    break

                kind = event["event"]
                name = event.get("name", "")
                metadata = event.get("metadata", {}) or {}
                langgraph_node = metadata.get("langgraph_node", "")

                if kind == "on_chat_model_end" and langgraph_node in ("explorer", "critic"):
                    data = event.get("data", {}) or {}
                    usage_meta = _extract_usage_metadata(data)
                    _accumulate_usage(usage_by_node[langgraph_node], usage_meta)

                if name not in ("explorer", "critic"):
                    continue

                if kind == "on_chain_start":
                    if current_status is not None:
                        current_status.stop()
                    current_status = console.status(
                        f"[cyan]→[/cyan] [bold]{name}[/bold] thinking...",
                        spinner="dots",
                    )
                    current_status.start()

                elif kind == "on_chain_end":
                    if current_status is not None:
                        current_status.stop()
                        current_status = None

                    data = event.get("data", {}) or {}
                    output = data.get("output", {}) or {}

                    if name == "explorer":
                        r = output.get("round", "?")
                        draft_text = output.get("draft", "") or ""
                        console.print(
                            f"[green]ok[/green] [bold]explorer[/bold] round {r} "
                            f"— draft generated ({len(draft_text)} chars)"
                        )
                    elif name == "critic":
                        passed = output.get("passed", False)
                        issues_list = output.get("issues", []) or []
                        resolved_list = output.get("resolved", []) or []
                        status_color = "green" if passed else "yellow"
                        suffix = (
                            f", resolved+{len(resolved_list)}" if resolved_list else ""
                        )
                        console.print(
                            f"[green]ok[/green] [bold]critic[/bold] "
                            f"— {len(issues_list)} issues, "
                            f"[{status_color}]passed={passed}[/{status_color}]{suffix}"
                        )
        except asyncio.CancelledError:
            interrupted = True
        finally:
            if current_status is not None:
                current_status.stop()
            # Tear down the ESC listener BEFORE running any UI logic below,
            # so stdin is back in canonical mode and termios is restored.
            cancel_event.set()
            esc_task.cancel()
            try:
                await esc_task
            except (asyncio.CancelledError, Exception):
                pass

        if interrupted:
            console.print()
            console.print(
                "[yellow]⚠ Interrupted — saving partial state from last checkpoint...[/yellow]"
            )

        console.print(Rule(style="dim"))

        final = await graph.aget_state(config)
        values = (final.values if final else {}) or {}

        finished_at = datetime.now(timezone.utc)
        total_tokens = sum(b["total_tokens"] for b in usage_by_node.values())

        status_bits = [
            f"rounds={values.get('round', '?')}",
            f"passed={values.get('passed', False)}",
            f"tokens={total_tokens:,}",
        ]
        if interrupted:
            status_bits.append("[yellow]interrupted[/yellow]")
        console.print(f"[bold]Final:[/bold] {', '.join(status_bits)}")
        console.print("")

        # Only show the full draft panel and remaining-issues list on a
        # normal (non-interrupted) finish. On interrupt the "final" state
        # is really just the last checkpoint — potentially mid-iteration —
        # and showing it as "Final Draft" is misleading. The same content
        # is still saved to data/refine/{id}/draft.md and issues.json.
        if not interrupted:
            draft_text = values.get("draft", "(no draft)")
            console.print(Panel(draft_text, title="Final Draft", border_style="cyan"))

            issues_list = values.get("issues") or []
            if issues_list:
                console.print("")
                console.print(f"[bold]Remaining issues ({len(issues_list)}):[/bold]")
                for issue in issues_list:
                    severity_color = {
                        "blocker": "red",
                        "major": "yellow",
                        "minor": "dim",
                    }.get(issue.severity, "white")
                    console.print(
                        f"  [[{severity_color}]{issue.severity}[/{severity_color}]] "
                        f"[dim]{issue.id}[/dim] {issue.summary}"
                    )

        session_dir = _save_refine_session(
            thread_id,
            raw_idea,
            values,
            started_at=started_at,
            finished_at=finished_at,
            usage_by_node=usage_by_node,
            interrupted=interrupted,
        )
        console.print("")
        console.print(f"[bold green]Session saved to:[/bold green] {session_dir}")
        console.print("  raw_idea.md  draft.md  issues.json  meta.json")
        console.print("")
        console.print(f"[dim]Thread ID: {thread_id}[/dim]")
        console.print(f"[dim]Resume: uv run maars refine --thread {thread_id}[/dim]")


if __name__ == "__main__":
    app()
