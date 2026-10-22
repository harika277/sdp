"""Tests the logic behind the Gradio app (no Gradio or Ollama needed). Run: python test_ui.py"""
import os
import shutil
import tempfile

os.environ["EMBED_BACKEND"] = "hash"
os.environ["LLM_BACKEND"] = "extractive"
os.environ["EMAIL_AGENT_DATA"] = tempfile.mkdtemp()

from ui_logic import DemoLogic  # noqa: E402


def main():
    ui = DemoLogic()
    assert "20 emails" in ui.status()

    # search + validation
    choices, msg = ui.search("hosting quotation expiring soon", "", "", "", 5)
    assert choices and choices[0][1] in ("e12", "e13"), choices
    assert ui.search("", "", "", "", 5)[0] == []
    assert "YYYY-MM-DD" in ui.search("x", "", "30/06/2026", "", 5)[1]
    choices, _ = ui.search("budget", "finance", "2026-08-01", "", 5)
    assert choices and all("Finance" in c[0] for c in choices)
    assert ui.search("zzz", "nobody-at-all", "", "", 5)[0] == []

    # open email -> thread + summary
    thread, summary = ui.open_email("e9")
    assert "BrightPath" in thread or "Sneha" in thread
    assert "Basic summary" in summary  # offline mode is labelled honestly

    # draft guards
    assert ui.make_draft(None, "x")[0] is None
    assert ui.make_draft("e9", "  ")[0] is None
    draft, msg = ui.make_draft("e11", "Agree to start in January")
    assert draft["status"] == "draft" and "NOT SENT" in msg

    # edit, then send gate
    assert "saved" in ui.save_draft(draft["id"], "Edited body")
    assert ui.agent.mailbox.get_draft(draft["id"])["body"] == "Edited body"
    for bad in ["", "send", "SEND wrong", ui.required_phrase(draft["id"]) + "!"]:
        assert ui.send(draft["id"], bad).startswith("NOT SENT"), bad
    assert ui.drafts_rows()[0][1] == "DRAFT"
    assert ui.send(draft["id"], ui.required_phrase(draft["id"])).startswith("Sent to")
    assert ui.drafts_rows()[0][1] == "SENT"
    assert ui.send(draft["id"], ui.required_phrase(draft["id"])).startswith("NOT SENT")  # no double send
    assert "cannot" in ui.save_draft(draft["id"], "late edit").lower() or "unsent" in ui.save_draft(draft["id"], "x").lower()

    # reset
    assert "reset" in ui.reset_demo().lower() and ui.drafts_rows() == []
    assert len(ui.mailbox_rows()) == 20

    shutil.rmtree(os.environ["EMAIL_AGENT_DATA"], ignore_errors=True)
    print("UI logic tests passed.")


if __name__ == "__main__":
    main()
