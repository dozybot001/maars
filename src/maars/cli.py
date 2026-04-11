"""CLI entry point."""

from __future__ import annotations

import typer

app = typer.Typer(help="MAARS — Multi-Agent Automated Research System")


@app.callback()
def _root() -> None:
    """MAARS — Multi-Agent Automated Research System."""


@app.command()
def hello() -> None:
    """Sanity check: prove the CLI wiring is alive."""
    typer.echo("MAARS CLI ready. (Step 1 of M1)")


@app.command()
def sanity() -> None:
    """Smoke-test the chat model by invoking it once."""
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
    """Run the Critic on a draft and print structured output."""
    from maars.agents.critic import critique_draft

    result = critique_draft(draft)

    passed_str = "YES" if result.passed else "NO"
    typer.echo(f"Passed: {passed_str}")
    typer.echo(f"Summary: {result.summary}")
    typer.echo("")
    typer.echo(f"Issues ({len(result.issues)}):")
    for issue in result.issues:
        typer.echo(f"  [{issue.id}] ({issue.severity}) {issue.summary}")
        typer.echo(f"    -> {issue.detail}")
    if result.resolved:
        typer.echo("")
        typer.echo(f"Resolved: {', '.join(result.resolved)}")


@app.command()
def draft(
    raw_idea: str = typer.Argument(..., help="The raw research idea to expand into a draft"),
) -> None:
    """Run the Explorer on a raw idea and print the draft proposal."""
    from maars.agents.explorer import draft_proposal

    result = draft_proposal(raw_idea)
    typer.echo(result)


@app.command()
def refine(
    raw_idea: str = typer.Argument(..., help="The raw research idea to refine"),
    thread_id: str = typer.Option("default", "--thread", help="Thread ID for checkpointing and resume"),
    fresh: bool = typer.Option(
        False, "--fresh", help="Start a new thread instead of resuming existing checkpoint"
    ),
) -> None:
    """Run the full Refine graph with streaming events and checkpoint-based resume."""
    import asyncio

    asyncio.run(_refine_async(raw_idea, thread_id, fresh))


async def _refine_async(raw_idea: str, thread_id: str, fresh: bool) -> None:
    import uuid

    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule

    from maars.config import CHECKPOINT_DB
    from maars.graphs.refine import build_refine_graph

    console = Console()
    CHECKPOINT_DB.parent.mkdir(parents=True, exist_ok=True)

    async with AsyncSqliteSaver.from_conn_string(str(CHECKPOINT_DB)) as checkpointer:
        graph = build_refine_graph(checkpointer)

        config: dict = {"configurable": {"thread_id": thread_id}}
        existing = await graph.aget_state(config)
        has_state = bool(existing and existing.values)

        if has_state and fresh:
            new_thread = f"{thread_id}-{uuid.uuid4().hex[:6]}"
            console.print(
                f"[yellow]--fresh: starting new thread [bold]{new_thread}[/bold] "
                f"(keeping [dim]{thread_id}[/dim] intact)[/yellow]"
            )
            thread_id = new_thread
            config = {"configurable": {"thread_id": thread_id}}
            has_state = False

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

        console.print("")
        console.print(f"[dim]Thread ID: {thread_id}[/dim]")
        console.print(
            f'[dim]Resume with: maars refine "..." --thread {thread_id}[/dim]'
        )


if __name__ == "__main__":
    app()
