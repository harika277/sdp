"""Email API layer: search source, draft creation, and a gated send.

`Mailbox` is a JSON-backed stand-in. To use a real account, implement the same
methods against Gmail/Graph (users.messages.list/get, users.drafts.create,
users.drafts.send) and keep the confirmation check in `send_draft` intact.
"""
import json
import uuid
from datetime import datetime, timezone

import config


class ConfirmationRequired(Exception):
    """Raised when send is attempted without the exact human confirmation."""


def required_confirmation(draft_id: str) -> str:
    return f"SEND {draft_id}"


class Mailbox:
    def __init__(self, path=config.MAILBOX_PATH):
        self.emails = json.loads(open(path, encoding="utf-8").read())
        self._by_id = {e["id"]: e for e in self.emails}

    # ---- read side -------------------------------------------------------
    def list_emails(self) -> list[dict]:
        return self.emails

    def get_email(self, email_id: str) -> dict:
        return self._by_id[email_id]

    def get_thread(self, thread_id: str) -> list[dict]:
        msgs = [e for e in self.emails if e["thread_id"] == thread_id]
        return sorted(msgs, key=lambda e: e["date"])

    # ---- drafts ----------------------------------------------------------
    def _load_drafts(self) -> dict:
        if config.DRAFTS_PATH.exists():
            return json.loads(config.DRAFTS_PATH.read_text())
        return {}

    def _save_drafts(self, drafts: dict) -> None:
        config.DRAFTS_PATH.write_text(json.dumps(drafts, indent=2))

    def create_draft(self, in_reply_to: str, body: str, subject: str | None = None) -> dict:
        """Creates a draft only. Nothing is sent."""
        orig = self.get_email(in_reply_to)
        draft = {
            "id": "d_" + uuid.uuid4().hex[:8],
            "status": "draft",
            "to": orig["from"],
            "subject": subject or ("Re: " + orig["subject"].removeprefix("Re: ")),
            "body": body,
            "in_reply_to": in_reply_to,
            "thread_id": orig["thread_id"],
            "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        drafts = self._load_drafts()
        drafts[draft["id"]] = draft
        self._save_drafts(drafts)
        return draft

    def get_draft(self, draft_id: str) -> dict:
        return self._load_drafts()[draft_id]

    def update_draft(self, draft_id: str, body: str) -> dict:
        drafts = self._load_drafts()
        if drafts[draft_id]["status"] != "draft":
            raise ValueError("Only unsent drafts can be edited")
        drafts[draft_id]["body"] = body
        self._save_drafts(drafts)
        return drafts[draft_id]

    # ---- send (guarded) --------------------------------------------------
    def send_draft(self, draft_id: str, confirmation: str) -> dict:
        """Sends only if `confirmation` equals 'SEND <draft_id>' exactly.

        The check lives here, not in the agent or LLM layer, so no code path
        can send without it.
        """
        if (confirmation or "").strip() != required_confirmation(draft_id):
            raise ConfirmationRequired(
                f"Not sent. Type exactly '{required_confirmation(draft_id)}' to confirm."
            )
        drafts = self._load_drafts()
        draft = drafts[draft_id]
        if draft["status"] == "sent":
            raise ValueError("Draft already sent")
        # --- real provider call would go here ---
        draft["status"] = "sent"
        draft["sent_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._save_drafts(drafts)
        log = json.loads(config.SENT_LOG_PATH.read_text()) if config.SENT_LOG_PATH.exists() else []
        log.append({k: draft[k] for k in ("id", "to", "subject", "sent_at")})
        config.SENT_LOG_PATH.write_text(json.dumps(log, indent=2))
        return draft
