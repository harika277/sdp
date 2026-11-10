"""FAISS index over emails, with metadata filters applied after vector search."""
import json
import sys

import numpy as np

import config

try:
    import faiss
except ImportError:  # fallback so the pipeline still runs where faiss-cpu is unavailable
    faiss = None
    print("WARNING: faiss not installed; using NumPy brute-force fallback "
          "(same results, no FAISS). Run `pip install faiss-cpu` for the real index.",
          file=sys.stderr)


class _NumpyFlatIP:
    """Minimal stand-in for faiss.IndexFlatIP (exact inner-product search)."""

    def __init__(self, dim):
        self.vecs = np.zeros((0, dim), dtype="float32")

    def add(self, v):
        self.vecs = np.vstack([self.vecs, v])

    def search(self, q, k):
        sims = q @ self.vecs.T
        k = min(k, sims.shape[1])
        idx = np.argsort(-sims, axis=1)[:, :k]
        return np.take_along_axis(sims, idx, axis=1), idx

    def save(self, path):
        with open(path, "wb") as f:
            np.save(f, self.vecs)

    @classmethod
    def load(cls, path):
        with open(path, "rb") as f:
            arr = np.load(f)
        obj = cls(arr.shape[1])
        obj.vecs = arr
        return obj


def email_to_text(e: dict) -> str:
    return f"Subject: {e['subject']}\nFrom: {e['from']}\nDate: {e['date']}\n\n{e['body'][:2000]}"


class EmailIndex:
    def __init__(self, embedder):
        self.embedder = embedder
        self.index = None
        self.ids: list[str] = []

    def build(self, emails: list[dict]) -> None:
        vecs = self.embedder.embed_documents([email_to_text(e) for e in emails])
        if faiss:
            self.index = faiss.IndexFlatIP(vecs.shape[1])  # cosine via normalised vectors
        else:
            self.index = _NumpyFlatIP(vecs.shape[1])
        self.index.add(vecs)
        self.ids = [e["id"] for e in emails]
        if faiss:
            faiss.write_index(self.index, str(config.INDEX_PATH))
        else:
            self.index.save(config.INDEX_PATH)
        config.META_PATH.write_text(json.dumps(self.ids))

    def load(self) -> bool:
        if config.INDEX_PATH.exists() and config.META_PATH.exists():
            self.index = (faiss.read_index(str(config.INDEX_PATH)) if faiss
                          else _NumpyFlatIP.load(config.INDEX_PATH))
            self.ids = json.loads(config.META_PATH.read_text())
            return True
        return False

    def search(self, query: str, emails_by_id: dict, k: int = 5,
               sender: str | None = None, after: str | None = None,
               before: str | None = None) -> list[dict]:
        """Returns [{'email':..., 'score':...}] best first. Dates are YYYY-MM-DD."""
        q = self.embedder.embed_query(query)
        fetch = min(len(self.ids), max(k * 5, 20))
        scores, idxs = self.index.search(q, fetch)
        out = []
        for s, i in zip(scores[0], idxs[0]):
            if i < 0:
                continue
            e = emails_by_id[self.ids[i]]
            day = e["date"][:10]
            if sender and sender.lower() not in e["from"].lower():
                continue
            if after and day < after:
                continue
            if before and day > before:
                continue
            out.append({"email": e, "score": float(s)})
            if len(out) == k:
                break
        return out

  
      
         
