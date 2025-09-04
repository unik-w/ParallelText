"""Ollama-based semantic sentence alignment.

This module provides semantic sentence alignment using Ollama
for external service-based embedding generation. Uses
multilingual embedding models to find semantically similar sentences
across language pairs with configurable parameters.

Key improvements over naive alignment:
- Semantic understanding vs line-by-line matching
- Handles different sentence boundary patterns
- Multilingual embedding support
- Configurable similarity thresholds
- External service architecture (no large model downloads)
- Intelligent chunking for large texts
"""

import logging
import numpy as np
from typing import List, Dict, Any, Optional
from scipy.spatial.distance import cosine
from tqdm import tqdm

from ..services.ollama_client import OllamaClient, OllamaEmbeddingError
from ..data_types import AlignedSentences
from .chunking import create_batch_processor
from ..config import load_config

logger = logging.getLogger(__name__)


class OllamaSemanticAligner:
    """Ollama-based semantic sentence aligner.

    Uses Ollama's embedding models to perform semantic sentence alignment
    between parallel texts in different languages with configuration support.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        model: Optional[str] = None,
        similarity_threshold: Optional[float] = None,
        ollama_host: Optional[str] = None,
        ollama_port: Optional[int] = None,
        chunking_strategy: str = "sliding_window",
    ):
        """Initialize the Ollama semantic aligner.

        Args:
            config_path: Path to configuration file (optional)
            model: Override model from config (optional)
            similarity_threshold: Override similarity threshold (optional)
            ollama_host: Override Ollama host from config (optional)
            ollama_port: Override Ollama port from config (optional)
            chunking_strategy: Text chunking strategy
        """
        # Load configuration
        self.config = load_config(config_path)

        # Override configuration with provided parameters
        if model is not None:
            self.config.ollama.model = model
        if similarity_threshold is not None:
            self.config.alignment.similarity_threshold = similarity_threshold
        if ollama_host is not None:
            self.config.ollama.host = ollama_host
        if ollama_port is not None:
            self.config.ollama.port = ollama_port

        # Initialize Ollama client with configuration
        self.ollama_client = OllamaClient(
            host=self.config.ollama.host,
            port=self.config.ollama.port,
            timeout=self.config.ollama.timeout,
        )

        # Create batch processor for chunking
        self.batch_processor = create_batch_processor(
            strategy=chunking_strategy,
            max_chunk_size=self.config.chunking.max_chunk_size,
            max_sentences_per_chunk=self.config.chunking.max_sentences_per_chunk,
            overlap_sentences=self.config.chunking.overlap_sentences,
            batch_size=self.config.chunking.batch_size,
            max_concurrent=self.config.chunking.max_concurrent,
        )

        # Store configuration values for easy access
        self.similarity_threshold = self.config.alignment.similarity_threshold

        # Validate Ollama setup and model
        self._validate_setup()

    def _validate_setup(self):
        """Validate Ollama connection and model availability."""
        print(
            f"🔗 Connecting to Ollama server at {self.config.ollama.host}:{self.config.ollama.port}..."
        )

        try:
            # Test connection
            available_models = self.ollama_client.list_available_models()
        except Exception as e:
            raise OllamaEmbeddingError(
                "Cannot connect to Ollama service. Please ensure Ollama is "
                "running and accessible at "
                f"{self.config.ollama.host}:{self.config.ollama.port}"
            ) from e

        print(f"✅ Connected! Available models: {len(available_models)}")

        # Resolve model name
        model_name = self._resolve_model_name(available_models)
        if model_name not in available_models:
            raise OllamaEmbeddingError(
                f'Model "{model_name}" not found on Ollama server. '
                f"Available models: {available_models}. "
                f"Install with: ollama pull {model_name}"
            )

        self.model_name = model_name
        print(f"🤖 Using model: {model_name}")
        logger.info(f"Ollama semantic aligner initialized with model: {model_name}")

    def _resolve_model_name(self, available_models: List[str]) -> str:
        """Resolve the best available model name."""

        # Helper function to check if a model is available (with or without :latest suffix)
        def find_model(model_name: str) -> Optional[str]:
            # First try exact match
            if model_name in available_models:
                return model_name
            # Then try with :latest suffix
            if f"{model_name}:latest" in available_models:
                return f"{model_name}:latest"
            # Try without :latest suffix (if model_name has it)
            if model_name.endswith(":latest"):
                base_name = model_name[:-7]  # Remove ':latest'
                if base_name in available_models:
                    return base_name
            return None

        # First try configured model
        found_model = find_model(self.config.ollama.model)
        if found_model:
            return found_model

        # Then try fallback models
        for fallback in self.config.ollama.fallback_models:
            found_model = find_model(fallback)
            if found_model:
                logger.info(f"Using fallback model: {found_model}")
                return found_model

        # If no models match, return the configured model for error reporting
        return self.config.ollama.model  # Check if default model is available
        model_name = self.ollama_client.default_model
        if not self.ollama_client.check_model_availability(model_name):
            available_models = self.ollama_client.list_available_models()
            raise OllamaEmbeddingError(
                f'Model "{model_name}" not available in Ollama. '
                f"Available models: {available_models}. "
                f"Install with: ollama pull {model_name}"
            )

        logger.info(f"Ollama semantic aligner initialized with model: " f"{model_name}")

    def _compute_embeddings(self, sentences: List[str]) -> np.ndarray:
        """Compute embeddings for sentences using efficient chunking.

        Args:
            sentences: List of sentences to embed

        Returns:
            Embedding matrix of shape (n_sentences, embedding_dim)

        Raises:
            OllamaEmbeddingError: If embedding generation fails
        """
        if not sentences:
            return np.array([])

        # For large inputs, disable overlap to avoid mapping issues
        temp_overlap = self.batch_processor.chunker.overlap_sentences
        if len(sentences) > 50:
            self.batch_processor.chunker.overlap_sentences = 0

        try:
            # Check if we need chunking
            if (
                len(sentences) <= self.batch_processor.chunker.max_sentences_per_chunk
                and sum(len(s) for s in sentences)
                <= self.batch_processor.chunker.max_chunk_size
            ):
                # Small enough to process directly
                try:
                    embeddings = self.ollama_client.get_embeddings(
                        sentences, model=self.model_name
                    )
                    return np.array(embeddings)
                except OllamaEmbeddingError as e:
                    logger.error(f"Failed to generate embeddings: {e}")
                    raise

            # Use chunking for large input
            print(f"🔗 Processing {len(sentences)} sentences with chunking...")

            # Get processing statistics
            chunks = self.batch_processor.chunker.chunk_sentences(sentences)
            stats = self.batch_processor.get_processing_stats([chunks], [])

            print(
                f'📊 Chunking: {stats["total_chunks"]} chunks, '
                f'~{stats["estimated_total_tokens"]} tokens, '
                f'{stats["estimated_api_calls"]} API calls'
            )

            all_embeddings = []

            # Add progress bar for chunk processing
            chunk_progress = tqdm(
                enumerate(chunks),
                total=len(chunks),
                desc="🤖 Generating embeddings",
                unit="chunk",
            )

            for chunk_idx, chunk in chunk_progress:
                # Update progress bar description
                chunk_progress.set_description(
                    f"🤖 Processing chunk {chunk_idx + 1}/{len(chunks)}"
                )

                try:
                    chunk_embeddings = self.ollama_client.get_embeddings(
                        chunk, model=self.model_name
                    )
                    all_embeddings.extend(chunk_embeddings)

                except OllamaEmbeddingError as e:
                    logger.error(f"Failed to process chunk {chunk_idx}: {e}")
                    raise

            chunk_progress.close()
            print(f"✅ Embedding generation complete!")

            # Ensure we have embeddings for all sentences
            if len(all_embeddings) != len(sentences):
                # Handle overlap/chunking mismatches by rebuilding mapping
                logger.warning(
                    f"Embedding count mismatch: {len(all_embeddings)} "
                    f"embeddings for {len(sentences)} sentences. "
                    f"Rebuilding mapping..."
                )
                all_embeddings = self._rebuild_embedding_mapping(
                    sentences, chunks, all_embeddings
                )

            return np.array(all_embeddings)

        finally:
            # Restore original overlap setting
            self.batch_processor.chunker.overlap_sentences = temp_overlap

    def _rebuild_embedding_mapping(
        self,
        original_sentences: List[str],
        chunks: List[List[str]],
        chunk_embeddings: List[List[float]],
    ) -> List[List[float]]:
        """Rebuild sentence-to-embedding mapping from overlapping chunks.

        Args:
            original_sentences: Original sentence list
            chunks: List of sentence chunks
            chunk_embeddings: Flat list of embeddings from all chunks

        Returns:
            List of embeddings aligned with original sentences
        """
        sentence_to_embedding = {}
        embedding_idx = 0

        # Map each sentence to its embedding (skip duplicates from overlap)
        for chunk in chunks:
            for sentence in chunk:
                if sentence not in sentence_to_embedding and embedding_idx < len(
                    chunk_embeddings
                ):
                    sentence_to_embedding[sentence] = chunk_embeddings[embedding_idx]
                    embedding_idx += 1
                elif sentence in sentence_to_embedding:
                    # Skip duplicate sentences, but don't increment embedding_idx
                    continue

        # Rebuild ordered list
        ordered_embeddings = []
        missing_count = 0

        for sentence in original_sentences:
            if sentence in sentence_to_embedding:
                ordered_embeddings.append(sentence_to_embedding[sentence])
            else:
                missing_count += 1
                logger.warning(f"Missing embedding for sentence: {sentence[:50]}...")

                # Instead of zero vector, try to find a similar sentence embedding
                # or regenerate this specific sentence
                try:
                    # Generate embedding for this specific sentence
                    single_embedding = self.ollama_client.get_embeddings(
                        [sentence], model=self.model_name
                    )
                    if single_embedding:
                        ordered_embeddings.append(single_embedding[0])
                    else:
                        # Fallback to zero vector only as last resort
                        embedding_dim = (
                            len(chunk_embeddings[0]) if chunk_embeddings else 1024
                        )
                        ordered_embeddings.append([0.0] * embedding_dim)
                except Exception as e:
                    logger.error(f"Failed to generate single embedding: {e}")
                    # Fallback to zero vector
                    embedding_dim = (
                        len(chunk_embeddings[0]) if chunk_embeddings else 1024
                    )
                    ordered_embeddings.append([0.0] * embedding_dim)

        if missing_count > 0:
            logger.warning(
                f"Had to handle {missing_count} missing embeddings out of {len(original_sentences)}"
            )

        return ordered_embeddings

    def _compute_similarity_matrix(
        self, source_embeddings: np.ndarray, target_embeddings: np.ndarray
    ) -> np.ndarray:
        """Compute cosine similarity matrix between source and target.

        Args:
            source_embeddings: Source sentence embeddings
            target_embeddings: Target sentence embeddings

        Returns:
            Similarity matrix of shape (n_source, n_target)
        """
        if source_embeddings.size == 0 or target_embeddings.size == 0:
            return np.array([])

        similarity_matrix = np.zeros((len(source_embeddings), len(target_embeddings)))

        for i, source_emb in enumerate(source_embeddings):
            for j, target_emb in enumerate(target_embeddings):
                # Check for zero vectors (which would cause NaN in cosine calculation)
                source_norm = np.linalg.norm(source_emb)
                target_norm = np.linalg.norm(target_emb)

                if source_norm == 0 or target_norm == 0:
                    # Zero vector similarity is 0
                    similarity = 0.0
                else:
                    try:
                        # Cosine similarity = 1 - cosine distance
                        similarity = 1 - cosine(source_emb, target_emb)
                        # Ensure similarity is not NaN
                        if np.isnan(similarity):
                            similarity = 0.0
                    except (ValueError, FloatingPointError):
                        similarity = 0.0

                similarity_matrix[i, j] = similarity

        return similarity_matrix

    def align_with_threshold(
        self, source_sentences: List[str], target_sentences: List[str]
    ) -> AlignedSentences:
        """Align sentences using similarity threshold method.

        Args:
            source_sentences: Source language sentences
            target_sentences: Target language sentences

        Returns:
            AlignedSentences with matched pairs

        Raises:
            OllamaEmbeddingError: If embedding generation fails
        """
        if not source_sentences or not target_sentences:
            return AlignedSentences(source=[], target=[])

        print(f"🎯 Starting semantic alignment:")
        print(f"   📝 Source: {len(source_sentences)} sentences")
        print(f"   📝 Target: {len(target_sentences)} sentences")
        print(f"   🎚️  Similarity threshold: {self.similarity_threshold}")

        # Generate embeddings
        print(f"🤖 Generating source embeddings...")
        source_embeddings = self._compute_embeddings(source_sentences)

        print(f"🤖 Generating target embeddings...")
        target_embeddings = self._compute_embeddings(target_sentences)

        # Compute similarity matrix
        print(f"🧮 Computing similarity matrix...")
        similarity_matrix = self._compute_similarity_matrix(
            source_embeddings, target_embeddings
        )

        # Find best alignments above threshold
        aligned_source = []
        aligned_target = []
        used_target_indices = set()

        for i, source_sent in enumerate(source_sentences):
            # Find best target match for this source sentence
            best_j = np.argmax(similarity_matrix[i])
            best_similarity = similarity_matrix[i, best_j]

            # Check if similarity meets threshold and target not used
            if (
                best_similarity >= self.similarity_threshold
                and best_j not in used_target_indices
            ):
                aligned_source.append(source_sent)
                aligned_target.append(target_sentences[best_j])
                used_target_indices.add(best_j)
            else:
                # No good match found, skip this source sentence
                logger.debug(
                    f"No alignment found for source sentence {i}: "
                    f"best similarity {best_similarity:.3f} "
                    f"< threshold {self.similarity_threshold}"
                )

        print(f"✅ Semantic alignment complete!")
        print(f"🎯 Found {len(aligned_source)} matched pairs")

        logger.info(
            f"Threshold alignment: {len(aligned_source)} pairs from "
            f"{len(source_sentences)} source, "
            f"{len(target_sentences)} target sentences"
        )

        return AlignedSentences(source=aligned_source, target=aligned_target)

    def align_with_dynamic_programming(
        self,
        source_sentences: List[str],
        target_sentences: List[str],
        gap_penalty: float = 0.1,
    ) -> AlignedSentences:
        """Align sentences using dynamic programming approach.

        Args:
            source_sentences: Source language sentences
            target_sentences: Target language sentences
            gap_penalty: Penalty for skipping sentences

        Returns:
            AlignedSentences with optimal alignment

        Raises:
            OllamaEmbeddingError: If embedding generation fails
        """
        if not source_sentences or not target_sentences:
            return AlignedSentences(source=[], target=[])

        # Generate embeddings
        source_embeddings = self._compute_embeddings(source_sentences)
        target_embeddings = self._compute_embeddings(target_sentences)

        # Compute similarity matrix
        similarity_matrix = self._compute_similarity_matrix(
            source_embeddings, target_embeddings
        )

        # Dynamic programming alignment
        m, n = len(source_sentences), len(target_sentences)
        dp = np.zeros((m + 1, n + 1))
        path = {}

        # Fill DP table
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                # Match: take similarity score
                match_score = dp[i - 1, j - 1] + similarity_matrix[i - 1, j - 1]

                # Skip source sentence (gap in target)
                skip_source = dp[i - 1, j] - gap_penalty

                # Skip target sentence (gap in source)
                skip_target = dp[i, j - 1] - gap_penalty

                # Choose best option
                options = [
                    (match_score, "match"),
                    (skip_source, "skip_source"),
                    (skip_target, "skip_target"),
                ]
                best_score, best_action = max(options, key=lambda x: x[0])

                dp[i, j] = best_score
                path[(i, j)] = best_action

        # Backtrack to find alignment
        aligned_source = []
        aligned_target = []
        i, j = m, n

        while i > 0 or j > 0:
            if i == 0:
                # Only target sentences left, skip them
                j -= 1
            elif j == 0:
                # Only source sentences left, skip them
                i -= 1
            else:
                action = path.get((i, j), "match")
                if action == "match":
                    aligned_source.append(source_sentences[i - 1])
                    aligned_target.append(target_sentences[j - 1])
                    i -= 1
                    j -= 1
                elif action == "skip_source":
                    i -= 1
                elif action == "skip_target":
                    j -= 1

        # Reverse to get correct order
        aligned_source.reverse()
        aligned_target.reverse()

        logger.info(
            f"DP alignment: {len(aligned_source)} pairs from "
            f"{len(source_sentences)} source, "
            f"{len(target_sentences)} target sentences"
        )

        return AlignedSentences(source=aligned_source, target=aligned_target)

    def align(
        self,
        source_sentences: List[str],
        target_sentences: List[str],
        method: str = "threshold",
    ) -> AlignedSentences:
        """Align sentences using specified method.

        Args:
            source_sentences: Source language sentences
            target_sentences: Target language sentences
            method: Alignment method ('threshold' or 'dynamic_programming')

        Returns:
            AlignedSentences with matched pairs

        Raises:
            ValueError: If method is not supported
            OllamaEmbeddingError: If embedding generation fails
        """
        if method == "threshold":
            return self.align_with_threshold(source_sentences, target_sentences)
        elif method == "dynamic_programming":
            return self.align_with_dynamic_programming(
                source_sentences, target_sentences
            )
        else:
            raise ValueError(
                f"Unsupported alignment method: {method}. "
                f'Use "threshold" or "dynamic_programming"'
            )

    def get_alignment_info(self) -> Dict[str, Any]:
        """Get information about the aligner configuration.

        Returns:
            Dictionary with aligner settings and model info
        """
        return {
            "model": self.ollama_client.default_model,
            "similarity_threshold": self.similarity_threshold,
            "ollama_host": self.ollama_client.base_url,
            "available_models": self.ollama_client.list_available_models(),
            "service_type": "ollama_external",
            "chunking_strategy": self.batch_processor.chunker.__class__.__name__,
            "max_chunk_size": self.batch_processor.chunker.max_chunk_size,
            "max_sentences_per_chunk": self.batch_processor.chunker.max_sentences_per_chunk,
            "batch_size": self.batch_processor.batch_size,
            "max_concurrent": self.batch_processor.max_concurrent,
        }


def create_ollama_semantic_aligner(**kwargs) -> OllamaSemanticAligner:
    """Create an OllamaSemanticAligner with default settings.

    Args:
        **kwargs: Arguments passed to OllamaSemanticAligner constructor
                 (handles both old and new parameter names for compatibility)

    Returns:
        Configured OllamaSemanticAligner instance
    """
    # Handle old parameter names for backward compatibility
    config_overrides = {}

    # Map old parameter names to constructor parameters
    if "similarity_threshold" in kwargs:
        config_overrides["similarity_threshold"] = kwargs.pop("similarity_threshold")

    if "model" in kwargs:
        config_overrides["model"] = kwargs.pop("model")
    elif "multilingual" in kwargs:
        # Handle the old 'multilingual' parameter
        config_overrides["model"] = kwargs.pop("multilingual")

    # Remove old chunking parameters (handled by config now)
    kwargs.pop("max_chunk_size", None)
    kwargs.pop("max_sentences_per_chunk", None)

    # Pass remaining kwargs to constructor
    return OllamaSemanticAligner(**config_overrides, **kwargs)
