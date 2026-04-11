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


if __name__ == "__main__":
    app()
