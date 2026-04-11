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


if __name__ == "__main__":
    app()
