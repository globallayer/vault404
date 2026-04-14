"""
Embedding-based semantic search for vault404.

Uses sentence-transformers with a lightweight model for local embedding generation.
Auto-installs sentence-transformers on first use if not available.
"""

import logging
import subprocess
import sys
from typing import Optional
import numpy as np

logger = logging.getLogger(__name__)

# Lazy-loaded model instance
_model = None
_model_load_attempted = False
_install_attempted = False

# Default model - small, fast, effective for code/error similarity
DEFAULT_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384  # Dimension for all-MiniLM-L6-v2


def _auto_install_dependencies():
    """Auto-install sentence-transformers if not available."""
    global _install_attempted

    if _install_attempted:
        return False

    _install_attempted = True

    logger.info("Installing sentence-transformers for semantic search (one-time setup)...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "sentence-transformers>=2.2.0"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("sentence-transformers installed successfully.")
        return True
    except subprocess.CalledProcessError as e:
        logger.warning(f"Failed to auto-install sentence-transformers: {e}")
        return False


def _load_model():
    """Lazy load the embedding model, auto-installing if needed."""
    global _model, _model_load_attempted

    if _model_load_attempted:
        return _model

    _model_load_attempted = True

    # Try to import, auto-install if missing
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        # Auto-install and retry
        if _auto_install_dependencies():
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                logger.warning("sentence-transformers import failed after install.")
                _model = None
                return _model
        else:
            logger.warning("Semantic search unavailable. Falling back to keyword matching.")
            _model = None
            return _model

    # Load the model
    try:
        logger.info(f"Loading embedding model: {DEFAULT_MODEL} (first run may download ~90MB)")
        _model = SentenceTransformer(DEFAULT_MODEL)
        logger.info("Embedding model loaded. Semantic search enabled.")
    except Exception as e:
        logger.warning(f"Failed to load embedding model: {e}")
        _model = None

    return _model


def is_available() -> bool:
    """Check if embedding functionality is available."""
    return _load_model() is not None


def get_embedding(text: str) -> Optional[list[float]]:
    """
    Generate embedding vector for text.

    Args:
        text: Text to embed (error message, solution, etc.)

    Returns:
        List of floats representing the embedding, or None if unavailable
    """
    model = _load_model()
    if model is None:
        return None

    try:
        # Truncate very long text to avoid issues
        text = text[:2000] if len(text) > 2000 else text
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    except Exception as e:
        logger.warning(f"Failed to generate embedding: {e}")
        return None


def get_embeddings_batch(texts: list[str]) -> Optional[list[list[float]]]:
    """
    Generate embeddings for multiple texts efficiently.

    Args:
        texts: List of texts to embed

    Returns:
        List of embedding vectors, or None if unavailable
    """
    model = _load_model()
    if model is None:
        return None

    try:
        # Truncate long texts
        texts = [t[:2000] if len(t) > 2000 else t for t in texts]
        embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return embeddings.tolist()
    except Exception as e:
        logger.warning(f"Failed to generate batch embeddings: {e}")
        return None


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """
    Calculate cosine similarity between two vectors.

    Args:
        vec1: First embedding vector
        vec2: Second embedding vector

    Returns:
        Similarity score between 0 and 1
    """
    if vec1 is None or vec2 is None:
        return 0.0

    try:
        a = np.array(vec1)
        b = np.array(vec2)

        # Handle zero vectors
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(np.dot(a, b) / (norm_a * norm_b))
    except Exception:
        return 0.0


def semantic_similarity(text1: str, text2: str) -> float:
    """
    Calculate semantic similarity between two texts.

    Args:
        text1: First text
        text2: Second text

    Returns:
        Similarity score between 0 and 1, or 0.0 if embeddings unavailable
    """
    emb1 = get_embedding(text1)
    emb2 = get_embedding(text2)

    if emb1 is None or emb2 is None:
        return 0.0

    return cosine_similarity(emb1, emb2)


def find_most_similar(
    query_embedding: list[float],
    candidate_embeddings: list[tuple[str, list[float]]],
    top_k: int = 10,
    threshold: float = 0.3
) -> list[tuple[str, float]]:
    """
    Find most similar items from candidates.

    Args:
        query_embedding: Embedding of the query text
        candidate_embeddings: List of (id, embedding) tuples
        top_k: Maximum number of results
        threshold: Minimum similarity threshold

    Returns:
        List of (id, similarity_score) tuples, sorted by similarity descending
    """
    if query_embedding is None or not candidate_embeddings:
        return []

    results = []
    for item_id, embedding in candidate_embeddings:
        if embedding is None:
            continue
        sim = cosine_similarity(query_embedding, embedding)
        if sim >= threshold:
            results.append((item_id, sim))

    # Sort by similarity descending
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_k]


def combine_text_for_embedding(error_message: str, context: Optional[dict] = None) -> str:
    """
    Combine error message and context into a single text for embedding.

    This creates a richer representation that captures both the error
    and its context (language, framework, etc.)

    Args:
        error_message: The error message
        context: Optional context dict with language, framework, etc.

    Returns:
        Combined text suitable for embedding
    """
    parts = [error_message]

    if context:
        if context.get("language"):
            parts.append(f"language: {context['language']}")
        if context.get("framework"):
            parts.append(f"framework: {context['framework']}")
        if context.get("database"):
            parts.append(f"database: {context['database']}")
        if context.get("category"):
            parts.append(f"category: {context['category']}")

    return " | ".join(parts)
