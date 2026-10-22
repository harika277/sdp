"""Embedding backends. Production: nomic-embed-text through Ollama.

nomic-embed-text expects task prefixes: "search_document: " for indexed text
and "search_query: " for queries. Vectors are L2-normalised so FAISS inner
product equals cosine similarity.
"""
import hashlib
import re

import numpy as np
import requests

import config


def _normalise(v: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(v, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (v / norms).astype("float32")


class OllamaEmbedder:
    def __init__(self, url: str = config.OLLAMA_URL, model: str = config.EMBED_MODEL):
        self.url, self.model = url.rstrip("/"), model

    def _embed(self, text: str) -> list[float]:
        r = requests.post(
            f"{self.url}/api/embeddings",
            json={"model": self.model, "prompt": text},
            timeout=120,
        )
        r.raise_for_status()
        return r.json()["embedding"]

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        vecs = [self._embed("search_document: " + t) for t in texts]
        return _normalise(np.array(vecs, dtype="float32"))

    def embed_query(self, text: str) -> np.ndarray:
        return _normalise(np.array([self._embed("search_query: " + text)], dtype="float32"))


class HashEmbedder:
    """Offline bag-of-words hashing embedder. For tests/demos without Ollama only."""

    dim = 768

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype="float32")
        toks = re.findall(r"[a-z0-9]+", text.lower())
        for t in toks + [a + "_" + b for a, b in zip(toks, toks[1:])]:
            h = int(hashlib.md5(t.encode()).hexdigest(), 16)
            v[h % self.dim] += 1.0 if (h >> 64) % 2 else -1.0
        return v

    def embed_documents(self, texts):
        return _normalise(np.stack([self._vec(t) for t in texts]))

    def embed_query(self, text):
        return _normalise(self._vec(text)[None, :])


def get_embedder():
    if config.EMBED_BACKEND == "hash":
        return HashEmbedder()
    return OllamaEmbedder()
