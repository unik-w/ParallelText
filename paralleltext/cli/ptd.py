import typer
from pathlib import Path
from typing import Optional
import re

from ..io.epub_read import load_epub
from ..text.segment import paragraphs_from_xhtml
from ..align.naive import align_one_to_one
from ..render.build import build_merged_epub

cli = typer.Typer(add_completion=False, no_args_is_help=True)

_SKIP_TITLE_PAT = re.compile(
    r"(table of contents|contents|toc|nav|cover|title\s*page|impressum|"
    r"inhaltsverzeichnis|copyright|license|licence|dedication|acknowledg)",
    re.I,
)
_MIN_SUBSTANTIVE_PARAS = 3


def _is_substantive(chapter) -> bool:
    title = (getattr(chapter, "title", "") or "").strip()
    if _SKIP_TITLE_PAT.search(title):
        return False
    # quick structural filter: need at least a handful of non-empty paragraphs
    paras = [p for p in paragraphs_from_xhtml(chapter.html) if p and p.strip()]
    return len(paras) >= _MIN_SUBSTANTIVE_PARAS


def _substantive_chapters(book, limit: Optional[int]) -> list:
    chs = [c for c in (book.chapters or []) if _is_substantive(c)]
    if limit and limit > 0:
        return chs[:limit]
    return chs


def _do_merge(
    src: str, tgt: str, out: str, chapters: int, cover_strategy: str = "diagonal"
) -> None:
    """Core implementation shared by root-callback and the 'merge' subcommand."""
    src_book = load_epub(src)
    tgt_book = load_epub(tgt)

    # chapters==0 -> merge ALL substantive chapters
    limit = chapters if chapters and chapters > 0 else None
    src_chaps = _substantive_chapters(src_book, limit)
    tgt_chaps = _substantive_chapters(tgt_book, limit)

    if not src_chaps or not tgt_chaps:
        raise typer.BadParameter(
            "No substantive chapters found in one or both EPUBs. "
            "Verify fixtures were generated correctly."
        )

    # If counts differ slightly, align up to the min to avoid truncation surprises.
    pair_count = min(len(src_chaps), len(tgt_chaps))
    if pair_count < (limit or float("inf")):
        typer.secho(
            f"Warning: requested {limit or 'all'} chapters but only {pair_count} pairs available; proceeding with {pair_count}.",
            fg=typer.colors.YELLOW,
        )

    per_chapter_units = []
    for s, t in zip(src_chaps[:pair_count], tgt_chaps[:pair_count]):
        # Extract paragraphs, filtering out empties and boilerplate-only nodes.
        s_paras = [p for p in paragraphs_from_xhtml(s.html) if p and p.strip()]
        t_paras = [p for p in paragraphs_from_xhtml(t.html) if p and p.strip()]

        if not s_paras or not t_paras:
            typer.secho(
                f"Warning: empty chapter content encountered (src='{getattr(s, 'title', 'N/A')}', "
                f"tgt='{getattr(t, 'title', 'N/A')}'). Skipping chapter.",
                fg=typer.colors.YELLOW,
            )
            continue

        units = align_one_to_one(s_paras, t_paras)
        per_chapter_units.append(units)

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    build_merged_epub(
        src_book,
        tgt_book,
        per_chapter_units,
        out,
        tgt_epub_path=tgt,
        src_epub_path=src,
        cover_strategy=cover_strategy,
    )
    typer.echo(f"Wrote {out}")


@cli.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    src: str = typer.Option(None, help="Path to foreign-language EPUB (e.g., DE)"),
    tgt: str = typer.Option(None, help="Path to English EPUB"),
    out: str = typer.Option("build/merged.epub", help="Output EPUB path"),
    chapters: int = typer.Option(
        0,
        help="How many chapters to merge. Use 0 to merge ALL substantive chapters.",
    ),
    cover_strategy: str = typer.Option(
        "diagonal", help="Cover generation strategy: 'diagonal' or 'side_by_side'"
    ),
):
    if ctx.invoked_subcommand:
        return
    # If user provided options at root level, treat it as a merge invocation.
    if src and tgt:
        _do_merge(src, tgt, out, chapters, cover_strategy)
    else:
        # No subcommand and not enough options → show help.
        raise typer.Exit(code=0)


@cli.command("merge")
def merge_cmd(
    src: str = typer.Option(..., help="Path to foreign-language EPUB (e.g., DE)"),
    tgt: str = typer.Option(..., help="Path to English EPUB"),
    out: str = typer.Option("build/merged.epub", help="Output EPUB path"),
    chapters: int = typer.Option(
        0,
        help="How many chapters to merge. Use 0 to merge ALL substantive chapters.",
    ),
    cover_strategy: str = typer.Option(
        "diagonal", help="Cover generation strategy: 'diagonal' or 'side_by_side'"
    ),
):
    """Merge the first N chapters from two minimal EPUBs into a single parallel EPUB."""
    _do_merge(src, tgt, out, chapters, cover_strategy)
