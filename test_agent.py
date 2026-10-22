"""Offline tests. Run: EMBED_BACKEND=hash LLM_BACKEND=extractive python test_agent.py"""
import os
import shutil
import tempfile

os.environ["EMBED_BACKEND"] = "hash"
os.environ["LLM_BACKEND"] = "extractive"
os.environ["EMAIL_AGENT_DATA"] = tempfile.mkdtemp()

from agent import EmailAgent  # noqa: E402
from email_api import ConfirmationRequired  # noqa: E402


def main():
    agent = EmailAgent()

    # 1. Retrieval
    top = agent.search_emails("Acme renewal discount pricing", k=3)[0]["email"]
    assert top["thread_id"] == "t1", top
    top = agent.search_emails("double billed invoice refund")[0]["email"]
    assert top["id"] == "e4", top

    # 2. Metadata filters
    res = agent.search_emails("contract", sender="priya")
    assert res and all("priya" in r["email"]["from"].lower() for r in res)
    res = agent.search_emails("budget", after="2026-08-01")
    assert all(r["email"]["date"][:10] >= "2026-08-01" for r in res)

    # 3. Summary covers the whole thread
    summary = agent.summarize("e1")
    assert "12 percent" in summary or "discount" in summary

    # 4. Draft is created but NOT sent
    draft = agent.create_draft("e3", "Confirm we will accept the 24 month term")
    assert draft["status"] == "draft" and draft["to"].startswith("Priya")
    assert agent.mailbox.get_draft(draft["id"])["status"] == "draft"

    # 5. Send refused without exact confirmation
    for bad in ["", "yes", "send", f"SEND {draft['id']}x", "SEND d_other"]:
        try:
            agent.send(draft["id"], bad)
            raise AssertionError(f"sent with bad confirmation {bad!r}")
        except ConfirmationRequired:
            pass
    assert agent.mailbox.get_draft(draft["id"])["status"] == "draft"

    # 6. Send works only with the exact phrase
    sent = agent.send(draft["id"], f"SEND {draft['id']}")
    assert sent["status"] == "sent"

    shutil.rmtree(os.environ["EMAIL_AGENT_DATA"], ignore_errors=True)
    print("All tests passed.")


if __name__ == "__main__":
    main()
