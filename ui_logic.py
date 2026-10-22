"""UI-independent logic behind the Gradio app (kept separate so it can be tested without Gradio)."""
import datetime as dt

import config
import summarizer
from agent import EmailAgent
from email_api import ConfirmationRequired, required_confirmation


def _clean_date(s):
    s = (s or "").strip()
    if not s:
        return None
    dt.date.fromisoformat(s)  # raises ValueError on bad input
    return s


def _name(addr: str) -> str:
    return addr.split("<")[0].strip() or addr


def thread_markdown(thread: list[dict]) -> str:
    parts = []
    for m in thread:
        parts.append(
            f"**{_name(m['from'])}** · {m['date'][:10]}  \n"
            f"*{m['subject']}*\n\n> {m['body']}"
        )
    return "\n\n---\n\n".join(parts)


class DemoLogic:
    def __init__(self):
        self.agent = EmailAgent()

    # ---- status ----------------------------------------------------------
    def status(self) -> str:
        n = len(self.agent.mailbox.list_emails())
        emb = ("nomic-embed-text (Ollama)" if config.EMBED_BACKEND == "ollama"
               else "offline hash embeddings (demo only)")
        return f"**Mailbox:** {n} emails  |  **Embeddings:** {emb}  |  **LLM:** {summarizer.llm_status()}"

    def reindex(self) -> str:
        return f"Re-indexed {self.agent.reindex()} emails."

    # ---- search ----------------------------------------------------------
    def search(self, query, sender, after, before, k):
        query = (query or "").strip()
        if not query:
            return [], "Type what you are looking for first."
        try:
            after, before = _clean_date(after), _clean_date(before)
        except ValueError:
            return [], "Dates must look like YYYY-MM-DD (for example 2026-06-30)."
        try:
            results = self.agent.search_emails(
                query, int(k), sender=(sender or "").strip() or None, after=after, before=before
            )
        except Exception as exc:  # e.g. Ollama not running while using nomic-embed-text
            return [], f"Search failed: {exc}. Is Ollama running? (or start with --offline)"
        if not results:
            return [], "No matching emails. Try fewer filters."
        choices = []
        for r in results:
            e = r["email"]
            label = f"{e['date'][:10]} | {_name(e['from'])} | {e['subject']}  (match {r['score']:.2f})"
            choices.append((label, e["id"]))
        return choices, f"Found {len(choices)} email(s). Select one to read its thread."

    # ---- open one email --------------------------------------------------
    def open_email(self, email_id):
        thread = self.agent.mailbox.get_thread(self.agent.by_id[email_id]["thread_id"])
        summary = self.agent.summarize(email_id)
        tag = ("AI summary" if summarizer.LAST_SOURCE == "llm"
               else "Basic summary (LLM not available, see status bar)")
        return thread_markdown(thread), f"**Thread summary** ({tag})\n\n{summary}"

    # ---- drafts ----------------------------------------------------------
    def make_draft(self, email_id, intent):
        if not email_id:
            return None, "Select an email first."
        if not (intent or "").strip():
            return None, "Tell me what the reply should say or achieve."
        draft = self.agent.create_draft(email_id, intent.strip())
        how = "AI draft" if summarizer.LAST_SOURCE == "llm" else "Basic template draft (LLM not available)"
        return draft, f"{how} created. Status: NOT SENT."

    def save_draft(self, draft_id, body):
        if not draft_id:
            return "No draft to save."
        try:
            self.agent.mailbox.update_draft(draft_id, body)
        except ValueError as exc:
            return str(exc)
        return "Edits saved. Status: NOT SENT."

    def send(self, draft_id, typed):
        if not draft_id:
            return "No draft yet. Generate one first."
        try:
            d = self.agent.send(draft_id, typed or "")
        except ConfirmationRequired as exc:
            return f"NOT SENT. {exc}"
        except ValueError as exc:
            return f"NOT SENT. {exc}"
        return f"Sent to {d['to']} at {d['sent_at']}. (Demo mode: logged, no real email leaves your machine.)"

    def required_phrase(self, draft_id) -> str:
        return required_confirmation(draft_id) if draft_id else ""

    # ---- tables ----------------------------------------------------------
    def drafts_rows(self):
        drafts = self.agent.mailbox._load_drafts()
        rows = [[d["id"], d["status"].upper(), d["to"], d["subject"], d.get("sent_at") or d["created"]]
                for d in drafts.values()]
        return sorted(rows, key=lambda r: r[4], reverse=True)

    def mailbox_rows(self):
        return [[e["id"], e["date"][:10], e["from"], e["subject"], e["thread_id"]]
                for e in sorted(self.agent.mailbox.list_emails(), key=lambda e: e["date"], reverse=True)]

    def reset_demo(self) -> str:
        for p in (config.DRAFTS_PATH, config.SENT_LOG_PATH):
            if p.exists():
                p.unlink()
        return "Demo reset: all drafts and the sent log were cleared."
