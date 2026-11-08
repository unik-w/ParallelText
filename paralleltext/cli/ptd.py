import typer
from pathlib import Path
from typing import Optional
import re

from ..io.epub_read import load_epub
from ..text.segment import paragraph_elements, paragraphs_from_xhtml
from ..align.naive import align_one_to_one
from ..align.lengths import align_lengths, plain_text
from ..render.build import build_merged_epub
from ..render.interleave import (
    add_translation_style,
    read_source_docs,
    translation_block,
    write_interleaved_epub,
)

cli = typer.Typer(add_completion=False, no_args_is_help=True)

_SKIP_TITLE_PAT = re.compile(
    r"(table of contents|contents|toc|nav|cover|title\s*page|impressum|"
    r"inhaltsverzeichnis|\binhalt\b|copyright|license|licence|dedication|acknowledg)",
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


def _align_by_chapter_index(src_chaps, tgt_chaps) -> list:
    """Pair chapters by position and zip their paragraphs (drops leftovers)."""
    per_chapter_units = []
    for s, t in zip(src_chaps, tgt_chaps):
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
    return per_chapter_units


def _paragraphs(chapter) -> list:
    return [p for p in paragraphs_from_xhtml(chapter.html) if p and p.strip()]


_WORD_RE = re.compile(r"[^\W\d_][\w'’-]*")


def _name_anchors(src_texts, tgt_texts):
    """Per-paragraph sets of words usable as cross-language anchors.

    An anchor is a capitalised word found in both books that never occurs in
    lowercase in either; in practice that leaves names (Paul, Arrakis, ...)
    and drops German common nouns and sentence-initial words.
    """

    def words(texts):
        per_para = [
            [w.replace("’", "'") for w in _WORD_RE.findall(t)] for t in texts
        ]
        caps = {w for ws in per_para for w in ws if w[0].isupper()}
        lower = {w.lower() for ws in per_para for w in ws if w[0].islower()}
        return per_para, caps, lower

    src_words, src_caps, src_lower = words(src_texts)
    tgt_words, tgt_caps, tgt_lower = words(tgt_texts)
    vocab = {
        w
        for w in src_caps & tgt_caps
        if len(w) > 2 and w.lower() not in src_lower and w.lower() not in tgt_lower
    }
    return (
        [frozenset(w for w in ws if w in vocab) for ws in src_words],
        [frozenset(w for w in ws if w in vocab) for ws in tgt_words],
    )


def _interleave_whole_book(src_path, src_chaps, tgt_chaps, tgt_lang: str) -> dict:
    """Align all paragraphs of both books at once and insert the translations.

    Alignment runs over the whole book, so it is robust to the two editions
    splitting chapters into files differently. Each matched translation is
    inserted right after its source paragraph, inside the source chapter's own
    XHTML; translation text with no source counterpart is left out.
    Returns {chapter file name: new XHTML} for the chapters that changed.
    """
    raw_docs = read_source_docs(src_path, [ch.file_name for ch in src_chaps])
    src_docs = [raw_docs[ch.file_name] for ch in src_chaps]
    src_elems, src_doc_idx = [], []
    for di, doc in enumerate(src_docs):
        for el in paragraph_elements(doc):
            if el.get_text(strip=True):
                src_elems.append(el)
                src_doc_idx.append(di)
    tgt_paras = [p for ch in tgt_chaps for p in _paragraphs(ch)]

    src_texts = [plain_text(str(el)) for el in src_elems]
    tgt_texts = [plain_text(p) for p in tgt_paras]
    src_anchors, tgt_anchors = _name_anchors(src_texts, tgt_texts)
    groups = align_lengths(
        [len(t) for t in src_texts],
        [len(t) for t in tgt_texts],
        src_anchors,
        tgt_anchors,
    )

    changed = set()
    for s_idx, t_idx in groups:
        tgt_html = "".join(tgt_paras[k] for k in t_idx if tgt_texts[k])
        if not s_idx or not tgt_html:
            continue
        last = src_elems[s_idx[-1]]
        doc = src_docs[src_doc_idx[s_idx[-1]]]
        last.insert_after(translation_block(doc, tgt_html, tgt_lang))
        changed.add(src_doc_idx[s_idx[-1]])

    out = {}
    for di in changed:
        add_translation_style(src_docs[di])
        out[src_chaps[di].file_name] = str(src_docs[di])
    return out


def _do_merge(
    src: str,
    tgt: str,
    out: str,
    chapters: int,
    cover_strategy: str = "diagonal",
    align: str = "length",
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

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    if align == "length":
        replaced = _interleave_whole_book(
            src, src_chaps, tgt_chaps, tgt_book.language or "und"
        )
        lang_pair = "-".join(
            (b.language or "?").split("-")[0].upper() for b in (src_book, tgt_book)
        )
        write_interleaved_epub(src, replaced, out, title_suffix=f" ({lang_pair})")
        typer.echo(f"Wrote {out}")
        return
    else:
        # If counts differ slightly, align up to the min to avoid truncation surprises.
        pair_count = min(len(src_chaps), len(tgt_chaps))
        if pair_count < (limit or float("inf")):
            typer.secho(
                f"Warning: requested {limit or 'all'} chapters but only {pair_count} pairs available; proceeding with {pair_count}.",
                fg=typer.colors.YELLOW,
            )
        per_chapter_units = _align_by_chapter_index(
            src_chaps[:pair_count], tgt_chaps[:pair_count]
        )

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
    align: str = typer.Option(
        "length",
        help="Alignment: 'length' (whole-book, by paragraph length) or 'naive' (zip by index)",
    ),
):
    if ctx.invoked_subcommand:
        return
    # If user provided options at root level, treat it as a merge invocation.
    if src and tgt:
        _do_merge(src, tgt, out, chapters, cover_strategy, align)
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
    align: str = typer.Option(
        "length",
        help="Alignment: 'length' (whole-book, by paragraph length) or 'naive' (zip by index)",
    ),
):
    """Merge the first N chapters from two minimal EPUBs into a single parallel EPUB."""
    _do_merge(src, tgt, out, chapters, cover_strategy, align)
