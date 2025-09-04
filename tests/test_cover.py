"""Tests for cover generation functionality."""

import pytest
from PIL import Image
import io
from pathlib import Path
from paralleltext.render.cover import (
    CoverGenerator,
    DiagonalSplitCoverGenerator,
    SideBySideCoverGenerator,
    extract_cover_from_epub,
    generate_combined_cover,
)


class TestCoverGenerator:
    """Test cover generation base functionality."""

    def test_cover_generator_is_abstract(self):
        """Test that CoverGenerator cannot be instantiated directly."""
        generator = CoverGenerator()

        # Should raise NotImplementedError
        with pytest.raises(NotImplementedError):
            generator.generate_cover(None, None)

    def create_test_image(self, color="red", size=(100, 150)):
        """Helper to create test image data."""
        img = Image.new("RGB", size, color=color)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()


class TestDiagonalSplitCoverGenerator:
    """Test diagonal split cover generation."""

    def create_test_image(self, color="red", size=(100, 150)):
        """Helper to create test image data."""
        img = Image.new("RGB", size, color=color)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    def test_diagonal_split_with_both_covers(self):
        """Test diagonal split with both source and target covers."""
        generator = DiagonalSplitCoverGenerator()

        src_data = self.create_test_image("blue")
        tgt_data = self.create_test_image("red")

        result = generator.generate_cover(src_data, tgt_data, (200, 300))

        assert isinstance(result, bytes)
        assert len(result) > 0

        # Should be valid image data
        img = Image.open(io.BytesIO(result))
        assert img.size == (200, 300)

    def test_diagonal_split_with_missing_src(self):
        """Test diagonal split with missing source cover."""
        generator = DiagonalSplitCoverGenerator()

        tgt_data = self.create_test_image("red")

        result = generator.generate_cover(None, tgt_data, (200, 300))

        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_diagonal_split_with_missing_tgt(self):
        """Test diagonal split with missing target cover."""
        generator = DiagonalSplitCoverGenerator()

        src_data = self.create_test_image("blue")

        result = generator.generate_cover(src_data, None, (200, 300))

        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_diagonal_split_with_no_covers(self):
        """Test diagonal split with no covers."""
        generator = DiagonalSplitCoverGenerator()

        result = generator.generate_cover(None, None, (200, 300))

        assert isinstance(result, bytes)
        assert len(result) > 0

        # Should create default cover
        img = Image.open(io.BytesIO(result))
        assert img.size == (200, 300)


class TestSideBySideCoverGenerator:
    """Test side-by-side cover generation."""

    def create_test_image(self, color="red", size=(100, 150)):
        """Helper to create test image data."""
        img = Image.new("RGB", size, color=color)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    def test_side_by_side_with_both_covers(self):
        """Test side-by-side with both covers."""
        generator = SideBySideCoverGenerator()

        src_data = self.create_test_image("blue")
        tgt_data = self.create_test_image("red")

        result = generator.generate_cover(src_data, tgt_data, (200, 300))

        assert isinstance(result, bytes)
        assert len(result) > 0

        img = Image.open(io.BytesIO(result))
        assert img.size == (200, 300)

    def test_side_by_side_with_missing_covers(self):
        """Test side-by-side with missing covers."""
        generator = SideBySideCoverGenerator()

        # Test with missing source
        tgt_data = self.create_test_image("red")
        result = generator.generate_cover(None, tgt_data, (200, 300))
        assert isinstance(result, bytes)

        # Test with missing target
        src_data = self.create_test_image("blue")
        result = generator.generate_cover(src_data, None, (200, 300))
        assert isinstance(result, bytes)

        # Test with both missing
        result = generator.generate_cover(None, None, (200, 300))
        assert isinstance(result, bytes)


class TestCoverExtraction:
    """Test cover extraction from EPUB files."""

    @pytest.fixture
    def test_epub_path(self):
        """Path to test EPUB file."""
        from pathlib import Path

        return Path(__file__).parent / "fixtures" / "de.epub"

    def test_extract_cover_from_existing_epub(self, test_epub_path):
        """Test extracting cover from existing EPUB."""
        if test_epub_path.exists():
            cover_data = extract_cover_from_epub(str(test_epub_path))

            if cover_data is not None:
                assert isinstance(cover_data, bytes)
                assert len(cover_data) > 0

                # Should be valid image data
                img = Image.open(io.BytesIO(cover_data))
                assert img.size[0] > 0
                assert img.size[1] > 0

    def test_extract_cover_from_nonexistent_epub(self):
        """Test extracting cover from non-existent EPUB."""
        cover_data = extract_cover_from_epub("nonexistent.epub")
        assert cover_data is None


class TestCombinedCoverGeneration:
    """Test high-level cover generation functions."""

    def create_test_image(self, color="red", size=(100, 150)):
        """Create test image data."""
        img = Image.new("RGB", size, color=color)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    @pytest.fixture
    def test_epub_paths(self):
        """Paths to test EPUB files."""
        from pathlib import Path

        base_path = Path(__file__).parent / "fixtures"
        return {"src": str(base_path / "de.epub"), "tgt": str(base_path / "en.epub")}

    def test_generate_combined_cover_diagonal(self, test_epub_paths):
        """Test generating combined cover with diagonal strategy."""
        if all(Path(p).exists() for p in test_epub_paths.values()):
            cover_data = generate_combined_cover(
                test_epub_paths["src"], test_epub_paths["tgt"], "diagonal"
            )

            assert isinstance(cover_data, bytes)
            assert len(cover_data) > 0

    def test_generate_combined_cover_side_by_side(self, test_epub_paths):
        """Test generating combined cover with side-by-side strategy."""
        if all(Path(p).exists() for p in test_epub_paths.values()):
            cover_data = generate_combined_cover(
                test_epub_paths["src"], test_epub_paths["tgt"], "side_by_side"
            )

            assert isinstance(cover_data, bytes)
            assert len(cover_data) > 0

    def test_generate_combined_cover_invalid_strategy(self, test_epub_paths):
        """Test generating cover with invalid strategy."""
        # Create dummy cover data
        dummy_cover = self.create_test_image()

        with pytest.raises(ValueError, match="Unsupported cover strategy"):
            generate_combined_cover(dummy_cover, dummy_cover, "invalid_strategy")
