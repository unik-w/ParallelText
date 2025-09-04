"""Efficient chunking strategies for Ollama semantic alignment.

This module provides intelligent chunking to optimize:
- API call efficiency (batch processing)
- Memory usage (manageable chunk sizes)
- Alignment quality (semantic coherence)
- Cost control (token/request limits)
"""

import logging
from typing import List, Tuple, Dict, Any
import re

logger = logging.getLogger(__name__)


class ChunkingStrategy:
    """Base class for text chunking strategies."""

    def __init__(
        self,
        max_chunk_size: int = 500,
        max_sentences_per_chunk: int = 20,
        overlap_sentences: int = 2,
    ):
        """Initialize chunking parameters.

        Args:
            max_chunk_size: Maximum characters per chunk
            max_sentences_per_chunk: Maximum sentences per chunk
            overlap_sentences: Sentences to overlap between chunks
        """
        self.max_chunk_size = max_chunk_size
        self.max_sentences_per_chunk = max_sentences_per_chunk
        self.overlap_sentences = overlap_sentences

    def chunk_sentences(self, sentences: List[str]) -> List[List[str]]:
        """Split sentences into manageable chunks.

        Args:
            sentences: List of sentences to chunk

        Returns:
            List of sentence chunks
        """
        raise NotImplementedError


class SlidingWindowChunker(ChunkingStrategy):
    """Sliding window chunking with overlap for context preservation."""

    def chunk_sentences(self, sentences: List[str]) -> List[List[str]]:
        """Chunk sentences using sliding window with overlap.

        Args:
            sentences: List of sentences to chunk

        Returns:
            List of overlapping sentence chunks
        """
        if not sentences:
            return []

        chunks = []
        i = 0

        while i < len(sentences):
            chunk = []
            chunk_chars = 0
            chunk_sentences = 0

            # Add sentences to chunk until limits reached
            for j in range(i, len(sentences)):
                sentence = sentences[j]
                sentence_chars = len(sentence)

                # Check if adding this sentence exceeds limits
                if (
                    chunk_sentences >= self.max_sentences_per_chunk
                    or chunk_chars + sentence_chars > self.max_chunk_size
                ):
                    break

                chunk.append(sentence)
                chunk_chars += sentence_chars
                chunk_sentences += 1

            if chunk:
                chunks.append(chunk)

            # Move window forward with overlap
            step = max(1, chunk_sentences - self.overlap_sentences)
            i += step

        logger.debug(
            f"Created {len(chunks)} chunks from {len(sentences)} "
            f"sentences (max_size={self.max_chunk_size}, "
            f"max_sentences={self.max_sentences_per_chunk})"
        )

        return chunks


class SemanticChunker(ChunkingStrategy):
    """Semantic boundary-aware chunking using punctuation and structure."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Patterns for semantic boundaries (strong breaks)
        self.strong_breaks = re.compile(r"[.!?]+\s*$")
        # Patterns for weak boundaries (commas, semicolons)
        self.weak_breaks = re.compile(r"[,;]+\s*$")

    def chunk_sentences(self, sentences: List[str]) -> List[List[str]]:
        """Chunk sentences at semantic boundaries.

        Args:
            sentences: List of sentences to chunk

        Returns:
            List of semantically coherent chunks
        """
        if not sentences:
            return []

        chunks = []
        current_chunk = []
        current_chars = 0

        for sentence in sentences:
            sentence_chars = len(sentence)

            # Check if adding sentence would exceed limits
            would_exceed = (
                len(current_chunk) >= self.max_sentences_per_chunk
                or current_chars + sentence_chars > self.max_chunk_size
            )

            if would_exceed and current_chunk:
                # Find a good break point in current chunk
                break_point = self._find_semantic_break(current_chunk)
                if break_point > 0:
                    # Split at semantic boundary
                    chunks.append(current_chunk[:break_point])
                    current_chunk = current_chunk[break_point:]
                    current_chars = sum(len(s) for s in current_chunk)
                else:
                    # No good break point, use entire chunk
                    chunks.append(current_chunk)
                    current_chunk = []
                    current_chars = 0

            current_chunk.append(sentence)
            current_chars += sentence_chars

        # Add remaining sentences
        if current_chunk:
            chunks.append(current_chunk)

        logger.debug(
            f"Semantic chunking: {len(chunks)} chunks from "
            f"{len(sentences)} sentences"
        )

        return chunks

    def _find_semantic_break(self, chunk: List[str]) -> int:
        """Find the best semantic break point in a chunk.

        Args:
            chunk: List of sentences in current chunk

        Returns:
            Index of best break point (0 = no good break)
        """
        # Look for strong sentence endings working backwards
        for i in range(len(chunk) - 1, 0, -1):
            sentence = chunk[i - 1]
            if self.strong_breaks.search(sentence.strip()):
                return i

        # Fallback: split in middle
        return len(chunk) // 2


class BatchProcessor:
    """Efficient batch processing for Ollama API calls."""

    def __init__(
        self, chunker: ChunkingStrategy, batch_size: int = 5, max_concurrent: int = 3
    ):
        """Initialize batch processor.

        Args:
            chunker: Chunking strategy to use
            batch_size: Number of chunks to process together
            max_concurrent: Maximum concurrent API calls
        """
        self.chunker = chunker
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent

    def prepare_batches(
        self, source_sentences: List[str], target_sentences: List[str]
    ) -> Tuple[List[List[str]], List[List[str]]]:
        """Prepare sentence batches for efficient processing.

        Args:
            source_sentences: Source language sentences
            target_sentences: Target language sentences

        Returns:
            Tuple of (source_chunks, target_chunks)
        """
        source_chunks = self.chunker.chunk_sentences(source_sentences)
        target_chunks = self.chunker.chunk_sentences(target_sentences)

        logger.info(
            f"Prepared batches: {len(source_chunks)} source chunks, "
            f"{len(target_chunks)} target chunks"
        )

        return source_chunks, target_chunks

    def estimate_tokens(self, chunks: List[List[str]]) -> int:
        """Estimate token count for chunks (rough approximation).

        Args:
            chunks: List of sentence chunks

        Returns:
            Estimated total tokens
        """
        total_chars = sum(sum(len(s) for s in chunk) for chunk in chunks)
        # Rough estimate: 1 token ≈ 4 characters
        return total_chars // 4

    def get_processing_stats(
        self, source_chunks: List[List[str]], target_chunks: List[List[str]]
    ) -> Dict[str, Any]:
        """Get statistics about the processing job.

        Args:
            source_chunks: Source sentence chunks
            target_chunks: Target sentence chunks

        Returns:
            Dictionary with processing statistics
        """
        source_tokens = self.estimate_tokens(source_chunks)
        target_tokens = self.estimate_tokens(target_chunks)

        return {
            "source_chunks": len(source_chunks),
            "target_chunks": len(target_chunks),
            "total_chunks": len(source_chunks) + len(target_chunks),
            "estimated_source_tokens": source_tokens,
            "estimated_target_tokens": target_tokens,
            "estimated_total_tokens": source_tokens + target_tokens,
            "estimated_api_calls": len(source_chunks) + len(target_chunks),
            "chunking_strategy": self.chunker.__class__.__name__,
        }


def create_chunking_strategy(
    strategy: str = "sliding_window", **kwargs
) -> ChunkingStrategy:
    """Create a chunking strategy.

    Args:
        strategy: Strategy type ('sliding_window' or 'semantic')
        **kwargs: Strategy-specific parameters

    Returns:
        Configured chunking strategy

    Raises:
        ValueError: If strategy is not supported
    """
    if strategy == "sliding_window":
        return SlidingWindowChunker(**kwargs)
    elif strategy == "semantic":
        return SemanticChunker(**kwargs)
    else:
        raise ValueError(f"Unsupported chunking strategy: {strategy}")


def create_batch_processor(
    chunking_strategy: str = "sliding_window", **kwargs
) -> BatchProcessor:
    """Create a batch processor with specified chunking strategy.

    Args:
        chunking_strategy: Chunking strategy to use
        **kwargs: Parameters for chunker and processor

    Returns:
        Configured batch processor
    """
    # Split kwargs between chunker and processor
    chunker_params = {
        k: v
        for k, v in kwargs.items()
        if k in ["max_chunk_size", "max_sentences_per_chunk", "overlap_sentences"]
    }
    processor_params = {
        k: v for k, v in kwargs.items() if k in ["batch_size", "max_concurrent"]
    }

    chunker = create_chunking_strategy(chunking_strategy, **chunker_params)
    return BatchProcessor(chunker, **processor_params)
