"""CLI entry point."""

from __future__ import annotations

import json
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


def _save_refine_session(
    thread_id: str,
    raw_idea: str,
    values: dict,
) -> Path:
    """Save final session artifacts under data/refine/{num}/.

    Writes:
        data/refine/{num}/raw_idea.md   -- the original input
        data/refine/{num}/draft.md      -- the final refined draft
        data/refine/{num}/issues.json   -- remaining unresolved issues
        data/refine/{num}/meta.json     -- run metadata
    """
    from maars.config import CHAT_MODEL, DATA_DIR, REFINE_MAX_ROUND

    num_str = thread_id.split("-", 1)[-1]
    session_dir = DATA_DIR / "refine" / num_str
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

    meta = {
        "thread_id": thread_id,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "model": CHAT_MODEL,
        "max_round": REFINE_MAX_ROUND,
        "final_round": values.get("round", 0),
        "passed": values.get("passed", False),
        "total_resolved": len(values.get("resolved") or []),
        "remaining_issues": {
            "blocker": blockers,
            "major": majors,
            "minor": minors,
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
    import asyncio

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

        async for event in graph.astream_events(input_state, config=config, version="v2"):
            kind = event["event"]
            name = event.get("name", "")

            if name not in ("explorer", "critic"):
                continue

            if kind == "on_chain_start":
                console.print(f"[cyan]->[/cyan] [bold]{name}[/bold] running...")
            elif kind == "on_chain_end":
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
                    suffix = f", resolved+{len(resolved_list)}" if resolved_list else ""
                    console.print(
                        f"[green]ok[/green] [bold]critic[/bold] "
                        f"— {len(issues_list)} issues, "
                        f"[{status_color}]passed={passed}[/{status_color}]{suffix}"
                    )

        console.print(Rule(style="dim"))

        final = await graph.aget_state(config)
        values = (final.values if final else {}) or {}

        console.print(
            f"[bold]Final:[/bold] rounds={values.get('round', '?')}, "
            f"passed={values.get('passed', False)}"
        )
        console.print("")

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

        session_dir = _save_refine_session(thread_id, raw_idea, values)
        console.print("")
        console.print(f"[bold green]Session saved to:[/bold green] {session_dir}")
        console.print("  raw_idea.md  draft.md  issues.json  meta.json")
        console.print("")
        console.print(f"[dim]Thread ID: {thread_id}[/dim]")
        console.print(f"[dim]Resume: uv run maars refine --thread {thread_id}[/dim]")


if __name__ == "__main__":
    app()
