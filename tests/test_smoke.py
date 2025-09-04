"""Smoke tests for basic functionality."""

from pathlib import Path
import tempfile
from paralleltext.io.epub_read import load_epub
from paralleltext.text.segment import paragraphs_from_xhtml
from paralleltext.align.naive import align_one_to_one
from paralleltext.render.build import build_merged_epub


def test_merge_smoke():
    """Test basic end-to-end merge functionality."""
    # Use the available fixtures
    root = Path(__file__).resolve().parents[1]
    src_path = root / "tests" / "fixtures" / "de.epub"
    tgt_path = root / "tests" / "fixtures" / "en.epub"

    assert (
        src_path.exists() and tgt_path.exists()
    ), f"Test fixtures missing. Expected {src_path} and {tgt_path}."

    # Load EPUBs
    src_book = load_epub(str(src_path))
    tgt_book = load_epub(str(tgt_path))

    assert src_book.chapters
    assert tgt_book.chapters

    # Process first chapter
    src_paras = paragraphs_from_xhtml(src_book.chapters[0].html)
    tgt_paras = paragraphs_from_xhtml(tgt_book.chapters[0].html)

    # Filter empty paragraphs
    src_paras = [p for p in src_paras if p.strip()]
    tgt_paras = [p for p in tgt_paras if p.strip()]

    assert src_paras and tgt_paras

    # Align and build
    units = align_one_to_one(src_paras, tgt_paras)

    with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
        output_path = f.name

    try:
        build_merged_epub(
            src_book,
            tgt_book,
            [units],  # One chapter
            output_path,
            tgt_epub_path=str(tgt_path),
            src_epub_path=str(src_path),
        )

        # Verify output
        assert Path(output_path).exists()
        assert Path(output_path).stat().st_size > 0

        # Load and verify merged book
        merged_book = load_epub(output_path)
        assert merged_book.chapters
        assert merged_book.title

    finally:
        Path(output_path).unlink(missing_ok=True)
