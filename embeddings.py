"""
Embeddings + language detection for LexiRAG.

Uses fastembed (ONNX runtime) with the SAME model as before
(all-MiniLM-L6-v2), so vectors already stored in the database stay valid.
No PyTorch -> far lower RAM and much faster cold start on small servers.
The model is loaded lazily on first use, not at import time.
"""
import os
import threading

import numpy as np
from langdetect import detect, DetectorFactory

DetectorFactory.seed = 0  # make language detection deterministic

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_CACHE_DIR = os.getenv("FASTEMBED_CACHE_DIR") or None

_model = None
_model_lock = threading.Lock()

SUPPORTED_LANGUAGES = {
    'hi': 'Hindi',
    'kn': 'Kannada',
    'ta': 'Tamil',
    'te': 'Telugu',
    'en': 'English'
}


def _get_model():
    """Load the embedding model once (thread-safe, lazy)."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from fastembed import TextEmbedding
                _model = TextEmbedding(model_name=MODEL_NAME, cache_dir=_CACHE_DIR)
    return _model


def _normalize(vec):
    vec = np.asarray(vec, dtype=np.float32)
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec


def detect_language(text):
    try:
        lang_code = detect(text[:500])
        return lang_code, SUPPORTED_LANGUAGES.get(lang_code, 'English')
    except Exception:
        return 'en', 'English'


def get_embedding(text):
    """Return one L2-normalised float32 vector (np.ndarray)."""
    return _normalize(next(iter(_get_model().embed([text]))))


def get_embeddings_batch(texts):
    """Return a list of L2-normalised float32 vectors, one per text."""
    return [_normalize(v) for v in _get_model().embed(list(texts))]
