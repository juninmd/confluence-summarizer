"""Command line: python -m src.cli backup|curate|verify <SPACE>."""

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable, Optional

import typer
from dotenv import load_dotenv

from src.backup.runner import backup_space
from src.backup.verify import verify_space
from src.curation.pipeline import curate_space
from src.db.pool import close_pg, init_pg
from src.services import confluence

load_dotenv("secrets/.env")
app = typer.Typer(help="Confluence backup and curation")


async def _with_services(job: Callable[[], Awaitable[Any]]) -> Any:
    await init_pg()
    await confluence.init_client()
    try:
        return await job()
    finally:
        await confluence.close_client()
        await close_pg()


_INDEX: Any = typer.Option(  # pyright: ignore[reportUnknownMemberType]
    True, help="Embed pages into pgvector"
)


@app.command()
def backup(space: str, index: bool = _INDEX) -> None:
    """Back up a space (raw, Markdown, images) incrementally."""
    manifest = asyncio.run(_with_services(lambda: backup_space(space, index=index)))
    typer.echo(f"{manifest['backed_up_pages']}/{manifest['expected_pages']} pages, "
               f"{len(manifest['errors'])} errors")  # fmt: skip
    raise typer.Exit(1 if manifest["errors"] else 0)


@app.command()
def verify(space: str) -> None:
    """Check files, links, images and checksums of a space backup."""
    problems = verify_space(space)
    for problem in problems:
        typer.echo(problem)
    typer.echo("OK" if not problems else f"{len(problems)} problem(s)")
    raise typer.Exit(1 if problems else 0)


@app.command()
def curate(space: str, threshold: Optional[float] = None) -> None:
    """Unify duplicates and refine every page of a backed-up space."""
    summary = asyncio.run(_with_services(lambda: curate_space(space, threshold)))
    typer.echo(json.dumps(summary, indent=2))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app()
