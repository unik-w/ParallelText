"""Configuration management for paralleltext."""

import os
import tomllib
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class OllamaConfig:
    """Ollama server configuration."""

    host: str
    port: int
    timeout: int
    model: str
    fallback_models: List[str]


@dataclass
class ChunkingConfig:
    """Text chunking configuration."""

    max_chunk_size: int
    max_sentences_per_chunk: int
    overlap_sentences: int
    batch_size: int
    max_concurrent: int


@dataclass
class AlignmentConfig:
    """Alignment processing configuration."""

    similarity_threshold: float
    fallback_to_naive: bool
    debug: bool


@dataclass
class ParalleltextConfig:
    """Complete paralleltext configuration."""

    ollama: OllamaConfig
    chunking: ChunkingConfig
    alignment: AlignmentConfig


def find_config_file() -> Optional[Path]:
    """Find configuration file in standard locations."""
    config_locations = [
        # Current directory
        Path.cwd() / "config.toml",
        Path.cwd() / ".paralleltext.toml",
        # User home directory
        Path.home() / ".paralleltext.toml",
        Path.home() / ".config" / "paralleltext.toml",
        # System-wide
        Path("/etc/paralleltext.toml"),
    ]

    for config_path in config_locations:
        if config_path.exists() and config_path.is_file():
            return config_path

    return None


def load_config(config_path: Optional[Path] = None) -> ParalleltextConfig:
    """Load configuration from TOML file with sensible defaults."""

    # Default configuration
    defaults = {
        "ollama": {
            "host": "localhost",
            "port": 11434,
            "timeout": 30,
            "model": "nomic-embed-text",
            "fallback_models": [
                "snowflake-arctic-embed2",
                "mxbai-embed-large",
                "all-minilm",
            ],
        },
        "chunking": {
            "max_chunk_size": 1000,
            "max_sentences_per_chunk": 10,
            "overlap_sentences": 2,
            "batch_size": 5,
            "max_concurrent": 3,
        },
        "alignment": {
            "similarity_threshold": 0.7,
            "fallback_to_naive": True,
            "debug": False,
        },
    }

    # Try to find config file if not provided
    if config_path is None:
        config_path = find_config_file()

    # Load from file if available
    if config_path and config_path.exists():
        try:
            with open(config_path, "rb") as f:
                file_config = tomllib.load(f)

            # Merge with defaults (file config overrides defaults)
            merged_config = _deep_merge(defaults, file_config)
        except Exception as e:
            print(f"Warning: Could not load config from {config_path}: {e}")
            print("Using default configuration.")
            merged_config = defaults
    else:
        merged_config = defaults

    # Create configuration objects
    ollama_config = OllamaConfig(**merged_config["ollama"])
    chunking_config = ChunkingConfig(**merged_config["chunking"])
    alignment_config = AlignmentConfig(**merged_config["alignment"])

    return ParalleltextConfig(
        ollama=ollama_config, chunking=chunking_config, alignment=alignment_config
    )


def _deep_merge(default: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries, with override taking precedence."""
    result = default.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def test_ollama_connection(config: OllamaConfig) -> bool:
    """Test connection to configured Ollama server."""
    try:
        import requests

        response = requests.get(
            f"http://{config.host}:{config.port}/api/version", timeout=config.timeout
        )

        if response.status_code == 200:
            version_info = response.json()
            print(f"✅ Connected to Ollama server at {config.host}:{config.port}")
            print(f"   Version: {version_info.get('version', 'unknown')}")
            return True
        else:
            print(f"❌ Ollama server responded with status {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Cannot connect to Ollama server at {config.host}:{config.port}")
        print(f"   Error: {e}")
        return False


def get_available_models(config: OllamaConfig) -> List[str]:
    """Get list of available models from Ollama server."""
    try:
        import requests

        response = requests.get(
            f"http://{config.host}:{config.port}/api/tags", timeout=config.timeout
        )

        if response.status_code == 200:
            data = response.json()
            models = data.get("models", [])
            return [model.get("name", "") for model in models]
        else:
            return []

    except Exception:
        return []


if __name__ == "__main__":
    # Test configuration loading
    print("🔧 Testing Configuration System")
    print("=" * 40)

    config = load_config()

    print(f"\n📝 Ollama Configuration:")
    print(f"   Host: {config.ollama.host}")
    print(f"   Port: {config.ollama.port}")
    print(f"   Model: {config.ollama.model}")
    print(f"   Fallback models: {config.ollama.fallback_models}")

    print(f"\n📊 Chunking Configuration:")
    print(f"   Max chunk size: {config.chunking.max_chunk_size}")
    print(f"   Max sentences per chunk: {config.chunking.max_sentences_per_chunk}")
    print(f"   Batch size: {config.chunking.batch_size}")

    print(f"\n🎯 Alignment Configuration:")
    print(f"   Similarity threshold: {config.alignment.similarity_threshold}")
    print(f"   Fallback to naive: {config.alignment.fallback_to_naive}")

    print(f"\n🌐 Testing Ollama Connection...")
    if test_ollama_connection(config.ollama):
        models = get_available_models(config.ollama)
        if models:
            print(f"📋 Available models: {models}")
        else:
            print("📋 No models found or could not retrieve model list")
    else:
        print("💡 Update the host in config.toml with your remote server IP")
