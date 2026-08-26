import typer
from pathlib import Path
from typing import Optional

from ..io.epub_read import load_epub
from ..text.segment import content_units_from_xhtml
from ..text.classify import split_front_body_back
from ..align import get_aligner
from ..align.chapter_match import match_chapters
from ..render.build import build_merged_epub

cli = typer.Typer(add_completion=False, no_args_is_help=True)


def _do_merge(
    src: str,
    tgt: str,
    out: str,
    chapters: int,
    cover_strategy: str = "diagonal",
    alignment_backend: str = "bertalign",
) -> None:
    """Core merge pipeline.

    1. Load EPUBs (unfiltered)
    2. Split each book into (front matter, body, back matter). Only leading/
       trailing runs of weak chapters are treated as front/back matter — a
       thin chapter sandwiched between two substantive ones stays in the body.
    3. Match source ↔ target body chapters
    4. For each matched pair: extract ContentUnits, run alignment
    5. Build merged EPUB: source front matter (verbatim) + aligned body +
       source back matter (verbatim)
    """
    typer.echo(f"Loading source EPUB: {src}")
    src_book = load_epub(src)
    typer.echo(f"Loading target EPUB: {tgt}")
    tgt_book = load_epub(tgt)

    typer.echo(
        f"  Source: {len(src_book.chapters)} raw chapters, "
        f"Target: {len(tgt_book.chapters)} raw chapters"
    )

    # Step 1: Split into front matter / body / back matter (boundary-only)
    typer.echo("Splitting front/back matter (start & end only)...")
    MIN_TEXT_UNITS = 30  # minimum text blocks to consider a chapter substantive
    src_front, src_content, src_back = split_front_body_back(
        src_book.chapters, min_text_units=MIN_TEXT_UNITS
    )
    _, tgt_content, _ = split_front_body_back(
        tgt_book.chapters, min_text_units=MIN_TEXT_UNITS
    )

    typer.echo(
        f"  Source: {len(src_front)} front, {len(src_content)} body, "
        f"{len(src_back)} back matter chapters"
    )
    typer.echo(f"  Target body: {len(tgt_content)} chapters")

    if not src_content or not tgt_content:
        raise typer.BadParameter(
            "No substantive chapters found in one or both EPUBs. "
            "Verify the EPUBs contain actual book content."
        )

    # Step 2: Match chapters across EPUBs
    typer.echo("Matching chapters across EPUBs...")
    use_embeddings = alignment_backend == "bertalign"
    chapter_pairs = match_chapters(
        src_content, tgt_content, use_embeddings=use_embeddings
    )

    # Keep only matched pairs (both sides present)
    matched_pairs = [(s, t) for s, t in chapter_pairs if s is not None and t is not None]

    if not matched_pairs:
        raise typer.BadParameter(
            "Could not match any chapters between source and target EPUBs."
        )

    typer.echo(f"  Matched {len(matched_pairs)} chapter pairs")

    # Apply chapter limit
    limit = chapters if chapters and chapters > 0 else None
    if limit:
        matched_pairs = matched_pairs[:limit]
        typer.echo(f"  Limited to {len(matched_pairs)} chapters")

    # Step 3: Align each matched pair
    aligner = get_aligner(alignment_backend)
    typer.echo(f"Aligning with backend: {alignment_backend}")

    per_chapter_units = []
    chapter_titles = []

    for i, (src_ch, tgt_ch) in enumerate(matched_pairs, start=1):
        typer.echo(
            f"  Chapter {i}: '{src_ch.title}' ↔ '{tgt_ch.title}'"
        )

        # Extract ContentUnits (preserving images and DOM order)
        src_units = content_units_from_xhtml(src_ch.html)
        tgt_units = content_units_from_xhtml(tgt_ch.html)

        src_text_count = sum(1 for u in src_units if u.kind == "TEXT")
        tgt_text_count = sum(1 for u in tgt_units if u.kind == "TEXT")
        src_img_count = sum(1 for u in src_units if u.kind == "IMAGE")

        if src_text_count == 0 or tgt_text_count == 0:
            typer.secho(
                f"  Warning: empty chapter content, skipping.",
                fg=typer.colors.YELLOW,
            )
            continue

        typer.echo(
            f"    src: {src_text_count} text + {src_img_count} images, "
            f"tgt: {tgt_text_count} text"
        )

        units = aligner(src_units, tgt_units)
        per_chapter_units.append(units)
        chapter_titles.append(src_ch.title or tgt_ch.title or f"Chapter {i}")

    if not per_chapter_units:
        raise typer.BadParameter("No chapters could be aligned.")

    # Step 4: Build merged EPUB
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    build_merged_epub(
        src_book,
        tgt_book,
        per_chapter_units,
        out,
        tgt_epub_path=tgt,
        src_epub_path=src,
        cover_strategy=cover_strategy,
        chapter_titles=chapter_titles,
        src_front_chapters=src_front,
        src_back_chapters=src_back,
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
    alignment_backend: str = typer.Option(
        "bertalign",
        help="Alignment backend: 'bertalign' (semantic, default) or 'naive' (1:1 zip)",
    ),
):
    if ctx.invoked_subcommand:
        return
    # If user provided options at root level, treat it as a merge invocation.
    if src and tgt:
        _do_merge(src, tgt, out, chapters, cover_strategy, alignment_backend)
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
    alignment_backend: str = typer.Option(
        "bertalign",
        help="Alignment backend: 'bertalign' (semantic, default) or 'naive' (1:1 zip)",
    ),
):
    """Merge chapters from two EPUBs into a single parallel EPUB."""
    _do_merge(src, tgt, out, chapters, cover_strategy, alignment_backend)

if __name__ == "__main__":
    cli()

