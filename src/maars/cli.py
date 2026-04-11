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
    thread_id: str = typer.Option("default", "--thread", help="Thread ID for checkpointing"),
) -> None:
    """Run the full Refine graph (Explorer <-> Critic loop)."""
    from maars.graphs.refine import build_refine_graph

    graph = build_refine_graph()

    initial_state = {"raw_idea": raw_idea, "round": 0}
    config = {"configurable": {"thread_id": thread_id}}

    result = graph.invoke(initial_state, config=config)

    typer.echo(f"Rounds: {result.get('round')}")
    typer.echo(f"Passed: {result.get('passed')}")
    typer.echo("")
    typer.echo("=== Final draft ===")
    typer.echo(result.get("draft", "(no draft)"))
    typer.echo("")
    issues = result.get("issues") or []
    typer.echo(f"=== Remaining issues ({len(issues)}) ===")
    for issue in issues:
        typer.echo(f"  [{issue.id}] ({issue.severity}) {issue.summary}")
    resolved = result.get("resolved") or []
    if resolved:
        typer.echo("")
        typer.echo(f"Resolved (accumulated): {', '.join(resolved)}")


if __name__ == "__main__":
    app()
