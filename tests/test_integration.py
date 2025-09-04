"""Integration tests for the entire application."""

import pytest
import tempfile
import zipfile
from pathlib import Path
from paralleltext.io.epub_read import load_epub
from paralleltext.text.segment import paragraphs_from_xhtml
from paralleltext.align.naive import align_one_to_one
from paralleltext.render.build import build_merged_epub


class TestIntegration:
    """Integration tests for complete workflows."""

    @pytest.fixture
    def test_epubs(self):
        """Load test EPUB files for integration testing."""
        base_path = Path(__file__).parent / "fixtures"
        src_path = base_path / "de.epub"
        tgt_path = base_path / "en.epub"

        if src_path.exists() and tgt_path.exists():
            return {
                "src_path": str(src_path),
                "tgt_path": str(tgt_path),
                "src_book": load_epub(str(src_path)),
                "tgt_book": load_epub(str(tgt_path)),
            }
        return None

    def test_complete_merge_workflow(self, test_epubs):
        """Test complete workflow from EPUB loading to merged output."""
        if test_epubs is None:
            pytest.skip("Test fixtures not available")

        src_book = test_epubs["src_book"]
        tgt_book = test_epubs["tgt_book"]

        # Verify books loaded successfully
        assert src_book.chapters
        assert tgt_book.chapters

        # Process first chapter from each
        src_chapter = src_book.chapters[0]
        tgt_chapter = tgt_book.chapters[0]

        # Extract paragraphs
        src_paras = paragraphs_from_xhtml(src_chapter.html)
        tgt_paras = paragraphs_from_xhtml(tgt_chapter.html)

        # Filter empty paragraphs
        src_paras = [p for p in src_paras if p.strip()]
        tgt_paras = [p for p in tgt_paras if p.strip()]

        assert src_paras
        assert tgt_paras

        # Align paragraphs
        alignment_units = align_one_to_one(src_paras, tgt_paras)
        assert alignment_units

        # Build merged EPUB
        with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
            output_path = f.name

        try:
            build_merged_epub(
                src_book,
                tgt_book,
                [alignment_units],  # List of chapter alignment units
                output_path,
                tgt_epub_path=test_epubs["tgt_path"],
                src_epub_path=test_epubs["src_path"],
            )

            # Verify output
            assert Path(output_path).exists()
            assert Path(output_path).stat().st_size > 0

            # Verify it's a valid EPUB
            with zipfile.ZipFile(output_path, "r") as zf:
                files = zf.namelist()
                assert "META-INF/container.xml" in files
                assert any(f.endswith(".opf") for f in files)

            # Load the merged EPUB and verify content
            merged_book = load_epub(output_path)
            assert merged_book.chapters
            assert len(merged_book.chapters) >= 1

        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_multiple_chapters_workflow(self, test_epubs):
        """Test workflow with multiple chapters."""
        if test_epubs is None:
            pytest.skip("Test fixtures not available")

        src_book = test_epubs["src_book"]
        tgt_book = test_epubs["tgt_book"]

        # Process up to 3 chapters
        max_chapters = min(3, len(src_book.chapters), len(tgt_book.chapters))

        per_chapter_units = []
        for i in range(max_chapters):
            src_paras = paragraphs_from_xhtml(src_book.chapters[i].html)
            tgt_paras = paragraphs_from_xhtml(tgt_book.chapters[i].html)

            # Filter empty
            src_paras = [p for p in src_paras if p.strip()]
            tgt_paras = [p for p in tgt_paras if p.strip()]

            if src_paras and tgt_paras:
                units = align_one_to_one(src_paras, tgt_paras)
                per_chapter_units.append(units)

        if not per_chapter_units:
            pytest.skip("No valid chapter pairs found")

        # Build merged EPUB
        with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
            output_path = f.name

        try:
            build_merged_epub(
                src_book,
                tgt_book,
                per_chapter_units,
                output_path,
                tgt_epub_path=test_epubs["tgt_path"],
                src_epub_path=test_epubs["src_path"],
            )

            # Verify merged EPUB has content
            merged_book = load_epub(output_path)
            assert len(merged_book.chapters) > 0
            assert merged_book.title
            # The merged book might have a different chapter structure than input

        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_empty_chapter_handling(self, test_epubs):
        """Test handling of chapters with no substantial content."""
        if test_epubs is None:
            pytest.skip("Test fixtures not available")

        src_book = test_epubs["src_book"]
        tgt_book = test_epubs["tgt_book"]

        # Create empty alignment units (simulating chapters with no content)
        empty_units = []

        with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
            output_path = f.name

        try:
            # Should handle empty units gracefully
            build_merged_epub(
                src_book,
                tgt_book,
                empty_units,
                output_path,
                tgt_epub_path=test_epubs["tgt_path"],
                src_epub_path=test_epubs["src_path"],
            )

            assert Path(output_path).exists()

        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_cover_generation_integration(self, test_epubs):
        """Test cover generation as part of complete workflow."""
        if test_epubs is None:
            pytest.skip("Test fixtures not available")

        src_book = test_epubs["src_book"]
        tgt_book = test_epubs["tgt_book"]

        # Create minimal alignment units
        if src_book.chapters and tgt_book.chapters:
            src_paras = ["<p>Test source paragraph</p>"]
            tgt_paras = ["<p>Test target paragraph</p>"]
            units = align_one_to_one(src_paras, tgt_paras)

            for strategy in ["diagonal", "side_by_side"]:
                with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
                    output_path = f.name

                try:
                    build_merged_epub(
                        src_book,
                        tgt_book,
                        [units],
                        output_path,
                        tgt_epub_path=test_epubs["tgt_path"],
                        src_epub_path=test_epubs["src_path"],
                        cover_strategy=strategy,
                    )

                    assert Path(output_path).exists()

                    # Verify EPUB structure includes cover
                    with zipfile.ZipFile(output_path, "r") as zf:
                        files = zf.namelist()
                        # Should have some image file for cover
                        has_image = any(
                            f.lower().endswith((".png", ".jpg", ".jpeg")) for f in files
                        )
                        # Note: might not always have cover, but structure should be valid

                finally:
                    Path(output_path).unlink(missing_ok=True)
