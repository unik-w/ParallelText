import typer
from pathlib import Path

from ..io.epub_read import load_epub
from ..text.segment import paragraphs_from_xhtml
from ..align.naive import align_one_to_one
from ..render.build import build_merged_epub

app = typer.Typer(add_completion=False)


@app.command()
def merge(
    src: str = typer.Option(..., help="Path to foreign-language EPUB (e.g., DE)"),
    tgt: str = typer.Option(..., help="Path to English EPUB"),
    out: str = typer.Option("build/merged.epub", help="Output EPUB path"),
    chapters: int = typer.Option(2, help="Number of chapters to merge (for M1 tests)"),
):
    src_book = load_epub(src)
    tgt_book = load_epub(tgt)

    # Limit to first N chapters for M1
    src_chaps = src_book.chapters[:chapters]
    tgt_chaps = tgt_book.chapters[:chapters]

    per_chapter_units = []
    for s, t in zip(src_chaps, tgt_chaps):
        s_paras = paragraphs_from_xhtml(s.html)
        t_paras = paragraphs_from_xhtml(t.html)
        units = align_one_to_one(s_paras, t_paras)
        per_chapter_units.append(units)

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    build_merged_epub(src_book, tgt_book, per_chapter_units, out)
    typer.echo(f"Wrote {out}")


if __name__ == "__main__":
    app()
