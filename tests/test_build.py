"""Tests for EPUB building and metadata functionality."""

import pytest
import tempfile
import zipfile
from pathlib import Path
from paralleltext.render.build import build_merged_epub, extract_epub_metadata
from paralleltext.io.epub_read import load_epub
from paralleltext.align.naive import align_one_to_one
from paralleltext.text.segment import paragraphs_from_xhtml


class TestMetadataExtraction:
    """Test metadata extraction functionality."""

    @pytest.fixture
    def test_epub_path(self):
        """Path to test EPUB file."""
        return Path(__file__).parent / "fixtures" / "de.epub"

    def test_extract_metadata_from_valid_epub(self, test_epub_path):
        """Test extracting metadata from valid EPUB."""
        if test_epub_path.exists():
            metadata = extract_epub_metadata(str(test_epub_path))

            assert isinstance(metadata, dict)
            assert "dc_metadata" in metadata
            assert "opf_metadata" in metadata
            assert "cover_info" in metadata
            assert "media_files" in metadata

            assert isinstance(metadata["dc_metadata"], dict)
            assert isinstance(metadata["opf_metadata"], list)

    def test_extract_metadata_from_nonexistent_file(self):
        """Test extracting metadata from non-existent file."""
        metadata = extract_epub_metadata("nonexistent.epub")

        # Should return default structure even on error
        assert isinstance(metadata, dict)
        assert "dc_metadata" in metadata
        assert "opf_metadata" in metadata


class TestEpubBuilding:
    """Test EPUB building functionality."""

    @pytest.fixture
    def test_epubs(self):
        """Load test EPUB files."""
        base_path = Path(__file__).parent / "fixtures"
        src_path = base_path / "de.epub"
        tgt_path = base_path / "en.epub"

        if src_path.exists() and tgt_path.exists():
            return {
                "src_book": load_epub(str(src_path)),
                "tgt_book": load_epub(str(tgt_path)),
                "src_path": str(src_path),
                "tgt_path": str(tgt_path),
            }
        return None

    @pytest.fixture
    def test_alignment_units(self, test_epubs):
        """Create test alignment units from test EPUBs."""
        if test_epubs is None:
            return None

        src_book = test_epubs["src_book"]
        tgt_book = test_epubs["tgt_book"]

        if not src_book.chapters or not tgt_book.chapters:
            return None

        # Take first chapter from each
        src_paras = paragraphs_from_xhtml(src_book.chapters[0].html)
        tgt_paras = paragraphs_from_xhtml(tgt_book.chapters[0].html)

        # Filter empty paragraphs
        src_paras = [p for p in src_paras if p.strip()]
        tgt_paras = [p for p in tgt_paras if p.strip()]

        if not src_paras or not tgt_paras:
            return None

        return [align_one_to_one(src_paras, tgt_paras)]

    def test_build_merged_epub_creates_file(self, test_epubs, test_alignment_units):
        """Test that building merged EPUB creates valid file."""
        if test_epubs is None or test_alignment_units is None:
            pytest.skip("Test fixtures not available")

        with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
            output_path = f.name

        try:
            build_merged_epub(
                test_epubs["src_book"],
                test_epubs["tgt_book"],
                test_alignment_units,
                output_path,
                tgt_epub_path=test_epubs["tgt_path"],
                src_epub_path=test_epubs["src_path"],
                cover_strategy="diagonal",
            )

            # Check that file was created
            assert Path(output_path).exists()
            assert Path(output_path).stat().st_size > 0

            # Check that it's a valid ZIP file (EPUB is ZIP)
            with zipfile.ZipFile(output_path, "r") as zf:
                file_list = zf.namelist()

                # Should contain required EPUB files
                assert "META-INF/container.xml" in file_list
                assert any(f.endswith(".opf") for f in file_list)

        finally:
            # Clean up
            Path(output_path).unlink(missing_ok=True)

    def test_build_merged_epub_with_different_strategies(
        self, test_epubs, test_alignment_units
    ):
        """Test building with different cover strategies."""
        if test_epubs is None or test_alignment_units is None:
            pytest.skip("Test fixtures not available")

        strategies = ["diagonal", "side_by_side"]

        for strategy in strategies:
            with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
                output_path = f.name

            try:
                build_merged_epub(
                    test_epubs["src_book"],
                    test_epubs["tgt_book"],
                    test_alignment_units,
                    output_path,
                    tgt_epub_path=test_epubs["tgt_path"],
                    src_epub_path=test_epubs["src_path"],
                    cover_strategy=strategy,
                )

                assert Path(output_path).exists()
                assert Path(output_path).stat().st_size > 0

            finally:
                Path(output_path).unlink(missing_ok=True)

    def test_build_merged_epub_preserves_metadata(
        self, test_epubs, test_alignment_units
    ):
        """Test that building preserves metadata from source EPUBs."""
        if test_epubs is None or test_alignment_units is None:
            pytest.skip("Test fixtures not available")

        with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
            output_path = f.name

        try:
            build_merged_epub(
                test_epubs["src_book"],
                test_epubs["tgt_book"],
                test_alignment_units,
                output_path,
                tgt_epub_path=test_epubs["tgt_path"],
                src_epub_path=test_epubs["src_path"],
            )

            # Load the generated EPUB and check metadata
            generated_book = load_epub(output_path)

            assert generated_book.title
            assert isinstance(generated_book.authors, list)
            assert isinstance(generated_book.language, str)
            assert len(generated_book.chapters) > 0

        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_build_with_empty_alignment_units(self, test_epubs):
        """Test building with empty alignment units."""
        if test_epubs is None:
            pytest.skip("Test fixtures not available")

        with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
            output_path = f.name

        try:
            build_merged_epub(
                test_epubs["src_book"],
                test_epubs["tgt_book"],
                [],  # Empty alignment units
                output_path,
                tgt_epub_path=test_epubs["tgt_path"],
                src_epub_path=test_epubs["src_path"],
            )

            # Should still create a valid file
            assert Path(output_path).exists()

        finally:
            Path(output_path).unlink(missing_ok=True)
