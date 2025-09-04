"""Integration tests for semantic alignment functionality."""

import pytest
from pathlib import Path

from paralleltext.align.ollama_semantic import OllamaSemanticAligner
from paralleltext.config import load_config
from paralleltext.text.sentence import sentences_from_xhtml
from paralleltext.io.epub_read import load_epub
from paralleltext.text.segment import paragraphs_from_xhtml


@pytest.fixture
def config():
    """Load configuration for tests."""
    return load_config()


@pytest.fixture
def sample_sentences():
    """Sample sentences for testing alignment."""
    source_sentences = [
        "Das ist ein Test.",
        "Dies ist ein weiterer Satz.",
        "Ein dritter Testsatz.",
    ]
    target_sentences = [
        "This is a test.",
        "This is another sentence.",
        "A third test sentence.",
    ]
    return source_sentences, target_sentences


class TestOllamaSemanticAligner:
    """Test the OllamaSemanticAligner class."""

    def test_aligner_initialization(self, config):
        """Test that the aligner can be initialized with config."""
        # Pass None as config_path to use defaults
        aligner = OllamaSemanticAligner(config_path=None)
        assert aligner.ollama_client is not None
        assert aligner.similarity_threshold is not None

    def test_small_scale_alignment(self, config, sample_sentences):
        """Test semantic alignment with a small set of sentences."""
        source_sentences, target_sentences = sample_sentences

        aligner = OllamaSemanticAligner(config_path=None)

        # Test alignment
        result = aligner.align(source_sentences, target_sentences)

        # Should have some aligned pairs
        assert len(result.source) > 0
        assert len(result.target) > 0
        assert len(result.source) == len(result.target)

        # All aligned sentences should be from the original sets
        for src in result.source:
            assert src in source_sentences
        for tgt in result.target:
            assert tgt in target_sentences

    def test_embedding_generation(self, config, sample_sentences):
        """Test that embeddings are generated correctly."""
        source_sentences, _ = sample_sentences

        aligner = OllamaSemanticAligner(config_path=None)
        embeddings = aligner._compute_embeddings(source_sentences)

        # Should have one embedding per sentence
        assert len(embeddings) == len(source_sentences)

        # Each embedding should be a list/array of numbers
        for embedding in embeddings:
            assert len(embedding) > 0
            assert all(isinstance(x, (int, float)) for x in embedding)

    def test_similarity_computation(self, config):
        """Test similarity computation between embeddings."""
        aligner = OllamaSemanticAligner(config_path=None)

        # Create some dummy embeddings (same embeddings should have high similarity)
        import numpy as np

        embedding1 = [1.0, 0.0, 0.0]
        embedding2 = [1.0, 0.0, 0.0]  # Same as embedding1
        embedding3 = [0.0, 1.0, 0.0]  # Different from embedding1

        embeddings1 = np.array([embedding1, embedding3])
        embeddings2 = np.array([embedding2, embedding3])

        similarity_matrix = aligner._compute_similarity_matrix(embeddings1, embeddings2)

        # Matrix should be 2x2
        assert similarity_matrix.shape == (2, 2)

        # Same embeddings should have high similarity (close to 1.0)
        assert similarity_matrix[0, 0] > 0.9

        # Different embeddings should have lower similarity
        assert similarity_matrix[0, 1] < similarity_matrix[0, 0]


class TestSemanticAlignmentIntegration:
    """Integration tests for the complete semantic alignment process."""

    def test_epub_semantic_alignment(self, config):
        """Test semantic alignment with actual EPUB files."""
        # Test files
        src_path = Path('tests/fixtures/de.epub')
        tgt_path = Path('tests/fixtures/en.epub')
        
        if not (src_path.exists() and tgt_path.exists()):
            pytest.skip('Test EPUB files not available')
        
        # Load EPUBs
        src_epub = load_epub(str(src_path))
        tgt_epub = load_epub(str(tgt_path))
        
        # Helper function to check if chapter is substantive
        def _is_substantive(chapter) -> bool:
            paras = [p for p in paragraphs_from_xhtml(chapter.html) 
                    if p and p.strip()]
            return len(paras) >= 3
        
        # Get first substantive chapter content
        src_chapters = [ch for ch in src_epub.chapters if _is_substantive(ch)]
        tgt_chapters = [ch for ch in tgt_epub.chapters if _is_substantive(ch)]
        
        assert len(src_chapters) > 0
        assert len(tgt_chapters) > 0
        
        # Extract sentences
        src_sentences = sentences_from_xhtml(src_chapters[0].html)
        tgt_sentences = sentences_from_xhtml(tgt_chapters[0].html)
        
        # Perform semantic alignment
        aligner = OllamaSemanticAligner(config_path=None)
        result = aligner.align(src_sentences, tgt_sentences)
        
        # Should find some matches
        assert len(result.source) > 0
        assert len(result.target) > 0
        
        # Alignment should be meaningful (more than a trivial number of matches)
        # Based on our test runs, we expect around 82 matches for the full content
        match_ratio = len(result.source) / min(len(src_sentences), len(tgt_sentences))
        assert match_ratio > 0.1  # At least 10% of sentences should match

    def test_embedding_consistency(self, config):
        """Test that embeddings are consistent across calls."""
        sentences = ["This is a test sentence.", "Another test sentence."]

        aligner = OllamaSemanticAligner(config_path=None)

        # Generate embeddings twice
        embeddings1 = aligner._compute_embeddings(sentences)
        embeddings2 = aligner._compute_embeddings(sentences)

        # Should be the same (assuming deterministic model)
        assert len(embeddings1) == len(embeddings2)
        for emb1, emb2 in zip(embeddings1, embeddings2):
            # Allow for small floating point differences
            assert len(emb1) == len(emb2)
            for v1, v2 in zip(emb1, emb2):
                assert abs(v1 - v2) < 1e-6

    def test_threshold_filtering(self, config, sample_sentences):
        """Test that similarity threshold is properly applied."""
        source_sentences, target_sentences = sample_sentences

        # Test with very high threshold (should find fewer matches)
        aligner_high = OllamaSemanticAligner(
            config_path=None, similarity_threshold=0.95
        )
        result_high = aligner_high.align(source_sentences, target_sentences)

        # Test with low threshold (should find more matches)
        aligner_low = OllamaSemanticAligner(config_path=None, similarity_threshold=0.1)
        result_low = aligner_low.align(source_sentences, target_sentences)

        # Low threshold should find at least as many matches as high threshold
        assert len(result_low.source) >= len(result_high.source)
