"""Central configuration. Override any value with an environment variable."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = Path(os.getenv("EMAIL_AGENT_DATA", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Mailbox source (mock JSON mailbox; swap in a real provider in email_api.py)
MAILBOX_PATH = Path(os.getenv("MAILBOX_PATH", BASE_DIR / "sample_emails.json"))
DRAFTS_PATH = DATA_DIR / "drafts.json"
SENT_LOG_PATH = DATA_DIR / "sent_log.json"

# Vector index
INDEX_PATH = DATA_DIR / "emails.faiss"
META_PATH = DATA_DIR / "emails_meta.json"

# Embeddings: "ollama" (nomic-embed-text) or "hash" (offline fallback for tests)
EMBED_BACKEND = os.getenv("EMBED_BACKEND", "ollama")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

# Summarizer / drafting LLM: "ollama" or "extractive" (no LLM, rule-based fallback)
LLM_BACKEND = os.getenv("LLM_BACKEND", "ollama")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1")

# The identity drafts are written as
USER_NAME = os.getenv("USER_NAME", "Arjun")
USER_EMAIL = os.getenv("USER_EMAIL", "arjun@example.com")
