"""Ollama service client for embeddings and language model tasks.

This module provides a modular interface to Ollama for:
- Text embeddings using various embedding models
- Future extensibility for other Ollama services

Supports multiple embedding models:
- snowflake-arctic-embed2 (568M): Latest multilingual model
- nomic-embed-text (137M): Popular, proven model
- mxbai-embed-large (335M): State-of-the-art large model
- bge-m3 (567M): Multi-functional, multi-lingual
- all-minilm (22M-33M): Lightweight option
"""

import logging
import requests
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


class OllamaEmbeddingError(Exception):
    """Exception raised for Ollama embedding service errors."""

    pass


class OllamaClient:
    """Client for Ollama API services.

    Provides modular access to Ollama's embedding models and future services.
    Designed for reusability across different project components.
    """

    DEFAULT_MODELS = {
        "multilingual": "snowflake-arctic-embed2",  # Latest 568M
        "popular": "nomic-embed-text",  # 137M most popular
        "large": "mxbai-embed-large",  # 335M state-of-the-art
        "lightweight": "all-minilm",  # 22M-33M efficient
        "versatile": "bge-m3",  # 567M multi-functional
    }

    def __init__(
        self,
        host: str = "localhost",
        port: int = 11434,
        timeout: int = 30,
        default_model: str = "multilingual",
    ):
        """Initialize Ollama client.

        Args:
            host: Ollama server host (default: localhost)
            port: Ollama server port (default: 11434)
            timeout: Request timeout in seconds (default: 30)
            default_model: Default embedding model key from DEFAULT_MODELS
        """
        self.base_url = f"http://{host}:{port}"
        self.timeout = timeout
        self.default_model = self.DEFAULT_MODELS.get(default_model, default_model)

    def _make_request(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make HTTP request to Ollama API.

        Args:
            endpoint: API endpoint (e.g., "/api/embed")
            data: Request payload

        Returns:
            Response JSON data

        Raises:
            OllamaEmbeddingError: If request fails or service unavailable
        """
        url = f"{self.base_url}{endpoint}"

        try:
            response = requests.post(
                url,
                json=data,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.ConnectionError:
            raise OllamaEmbeddingError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Please ensure Ollama is running with: ollama serve"
            )
        except requests.exceptions.Timeout:
            raise OllamaEmbeddingError(
                f"Request to Ollama timed out after {self.timeout} seconds"
            )
        except requests.exceptions.HTTPError as e:
            error_msg = f"Ollama API error: {e.response.status_code}"
            try:
                error_detail = e.response.json().get("error", "Unknown")
                error_msg += f" - {error_detail}"
            except requests.exceptions.JSONDecodeError:
                pass
            raise OllamaEmbeddingError(error_msg)
        except (ValueError, TypeError, KeyError) as e:
            raise OllamaEmbeddingError(f"Unexpected error: {str(e)}")

    def get_embeddings(
        self, texts: List[str], model: Optional[str] = None
    ) -> List[List[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            model: Embedding model name (uses default if None)

        Returns:
            List of embedding vectors (one per input text)

        Raises:
            OllamaEmbeddingError: If embedding generation fails
        """
        if not texts:
            return []

        model = model or self.default_model

        try:
            # Ollama expects a single input for embedding API
            embeddings = []
            for text in texts:
                data = {"model": model, "input": text}

                response = self._make_request("/api/embed", data)

                if "embeddings" not in response:
                    raise OllamaEmbeddingError(
                        "Invalid response format: missing embeddings field"
                    )

                # Ollama returns embeddings as a list of lists, take first
                embedding = response["embeddings"][0]
                embeddings.append(embedding)

            return embeddings

        except OllamaEmbeddingError:
            raise
        except (ValueError, TypeError, KeyError) as e:
            raise OllamaEmbeddingError(f"Error generating embeddings: {e}")

    def get_embedding(self, text: str, model: Optional[str] = None) -> List[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed
            model: Embedding model name (uses default if None)

        Returns:
            Embedding vector

        Raises:
            OllamaEmbeddingError: If embedding generation fails
        """
        embeddings = self.get_embeddings([text], model)
        return embeddings[0] if embeddings else []

    def check_model_availability(self, model: str) -> bool:
        """Check if a model is available in Ollama.

        Args:
            model: Model name to check

        Returns:
            True if model is available, False otherwise
        """
        try:
            # Try to get a small embedding to test model availability
            self.get_embedding("test", model)
            return True
        except OllamaEmbeddingError:
            return False

    def list_available_models(self) -> List[str]:
        """List models available in local Ollama instance.

        Returns:
            List of available model names

        Note:
            This is a best-effort implementation. Ollama API doesn't
            always provide a direct way to list only embedding models.
        """
        try:
            url = f"{self.base_url}/api/tags"
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            if "models" in data:
                return [model.get("name", "") for model in data["models"]]
            return []

        except Exception as e:
            logger.warning(f"Could not list available models: {e}")
            return []

    def get_recommended_model(self, use_case: str = "multilingual") -> str:
        """Get recommended model for specific use case.

        Args:
            use_case: One of "multilingual", "popular", "large",
                     "lightweight", "versatile"

        Returns:
            Recommended model name
        """
        return self.DEFAULT_MODELS.get(use_case, self.default_model)

    def validate_connection(self) -> bool:
        """Validate connection to Ollama service.

        Returns:
            True if Ollama is accessible and responsive
        """
        try:
            # Simple health check with a minimal embedding
            self.get_embedding("test")
            return True
        except OllamaEmbeddingError:
            return False


def create_ollama_client(**kwargs) -> OllamaClient:
    """Create an OllamaClient with default settings.

    Args:
        **kwargs: Arguments passed to OllamaClient constructor

    Returns:
        Configured OllamaClient instance
    """
    return OllamaClient(**kwargs)
