# Project 14: Email Search and Drafting Agent

Find an old email by meaning, summarise its thread, draft a reply, and send only after explicit human confirmation.

**Vector DB:** FAISS (`IndexFlatIP` over L2-normalised vectors = cosine similarity)
**Embeddings:** `nomic-embed-text` via Ollama (uses `search_document:` / `search_query:` prefixes)

## Architecture

```
query ──> embed_query ──> FAISS top-k ──> filters (sender/date) ──> results
                                                         │ pick
                                   thread fetch ──> summarizer ──> summary
                                                         │ + your intent
                                              draft_reply ──> create_draft (status=draft)
                                                         │ review / edit
                          send_draft(id, confirmation) ──X unless confirmation == "SEND <draft_id>"
```

| File | Role |
|---|---|
| `email_api.py` | Email search source, draft creation API, **gated send** (check enforced here, below the LLM layer) |
| `embeddings.py` | Ollama nomic-embed-text embedder, plus offline hash fallback for tests |
| `index.py` | FAISS build, persist, search with sender/date filters |
| `summarizer.py` | Thread summary and reply drafting (Ollama LLM, rule-based fallback) |
| `agent.py` | Tool wiring and interactive CLI |
| `app.py` | **Gradio web UI** (search, thread summary, draft editor, confirmation-gated send) |
| `ui_logic.py` | UI-independent logic behind the app (testable without Gradio) |
| `test_agent.py`, `test_ui.py` | Offline tests for retrieval, filters, drafts, the send gate, and the UI logic |
| `sample_emails.json` | 20 fake emails across 14 threads for the demo |

## Setup

```bash
pip install -r requirements.txt
ollama pull nomic-embed-text
ollama pull llama3.1          # optional, for LLM summaries/drafts
python agent.py reindex
python agent.py search "pricing terms for the Acme renewal" --sender priya
python agent.py run           # interactive: search -> summary -> draft -> confirm -> send
```

### Web UI (Gradio)

```bash
python app.py              # full mode: nomic-embed-text + llama3.1 via Ollama
python app.py --offline    # no Ollama needed (keyword-ish search, template drafts)
```
Open http://127.0.0.1:7860. A status bar shows whether Ollama and the LLM are actually in use. In the UI: search, pick a result, read the summary, describe your reply, generate and edit the draft, then type the shown `SEND <draft_id>` phrase to send (demo mode only logs it). The "Admin" tab rebuilds the index or clears drafts.

Run tests with no Ollama: `python test_agent.py` and `python test_ui.py`

## Safety design

- Drafting never sends. `create_draft` only writes a draft with `status="draft"`.
- `send_draft` refuses unless the confirmation string is exactly `SEND <draft_id>`. The CLI makes the human type it; the agent and LLM cannot supply it.
- Email bodies are treated as untrusted data in prompts (prompt-injection mitigation); the model is told not to follow instructions found in emails.
- Drafts must be unsent to be edited; a sent draft cannot be sent twice.

## Plugging in a real mailbox

Replace `Mailbox` in `email_api.py` with Gmail API (`users.messages.list/get`, `users.drafts.create`, `users.drafts.send`) or Microsoft Graph, keeping `send_draft`'s confirmation check. Point `reindex` at the fetched messages. For long emails, chunk bodies and keep a chunk-to-email id map in `index.py`.

## Possible extensions

Chunked embeddings for long threads, hybrid BM25 + vector search, IVF/HNSW index for large mailboxes, incremental indexing, reranking, and attachment text extraction.
