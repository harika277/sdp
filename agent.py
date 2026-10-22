"""Email Search & Drafting Agent.

Flow: search (FAISS) -> pick -> summarise thread -> draft reply -> human review
-> optional send, only after typing the exact confirmation phrase.

Usage:
    python agent.py reindex
    python agent.py search "pricing terms for the Acme renewal" [--sender priya] [--after 2026-01-01]
    python agent.py run                # interactive
"""
import argparse

import config
from email_api import ConfirmationRequired, Mailbox, required_confirmation
from embeddings import get_embedder
from index import EmailIndex
from summarizer import draft_reply, summarize_thread


class EmailAgent:
    def __init__(self):
        self.mailbox = Mailbox()
        self.by_id = {e["id"]: e for e in self.mailbox.list_emails()}
        self.index = EmailIndex(get_embedder())
        # Rebuild if there is no saved index or the mailbox changed since it was built.
        if not self.index.load() or self.index.ids != [e["id"] for e in self.mailbox.list_emails()]:
            self.reindex()

    # ---- tools -----------------------------------------------------------
    def reindex(self) -> int:
        emails = self.mailbox.list_emails()
        self.index.build(emails)
        return len(emails)

    def search_emails(self, query: str, k: int = 5, **filters) -> list[dict]:
        return self.index.search(query, self.by_id, k=k, **filters)

    def summarize(self, email_id: str) -> str:
        thread = self.mailbox.get_thread(self.by_id[email_id]["thread_id"])
        return summarize_thread(thread)

    def create_draft(self, email_id: str, intent: str) -> dict:
        thread = self.mailbox.get_thread(self.by_id[email_id]["thread_id"])
        body = draft_reply(thread, intent)
        return self.mailbox.create_draft(email_id, body)  # draft only, never sends

    def send(self, draft_id: str, confirmation: str) -> dict:
        return self.mailbox.send_draft(draft_id, confirmation)


# ---- CLI -----------------------------------------------------------------
def _print_results(results):
    if not results:
        print("No matching emails.")
    for n, r in enumerate(results, 1):
        e = r["email"]
        print(f"{n}. [{e['id']}] {e['date'][:10]}  {e['from']}\n   {e['subject']}  (score {r['score']:.2f})")


def interactive(agent: EmailAgent):
    query = input("What email are you looking for? > ").strip()
    results = agent.search_emails(query)
    _print_results(results)
    if not results:
        return
    pick = int(input("Pick a result number to reply to > ")) - 1
    email_id = results[pick]["email"]["id"]

    print("\n--- Thread summary ---\n" + agent.summarize(email_id))
    intent = input("\nWhat should your reply say / achieve? > ").strip()
    draft = agent.create_draft(email_id, intent)

    while True:
        print(f"\n--- Draft {draft['id']} (NOT SENT) ---\nTo: {draft['to']}\nSubject: {draft['subject']}\n\n{draft['body']}\n")
        action = input("[e]dit / [s]end / [q]uit (draft is saved) > ").strip().lower()
        if action == "e":
            print("Enter new body, finish with a line containing only END:")
            lines = []
            while (line := input()) != "END":
                lines.append(line)
            draft = agent.mailbox.update_draft(draft["id"], "\n".join(lines))
        elif action == "s":
            phrase = required_confirmation(draft["id"])
            typed = input(f"To send to {draft['to']}, type exactly '{phrase}' > ")
            try:
                agent.send(draft["id"], typed)
                print("Sent.")
            except ConfirmationRequired as exc:
                print(exc)
                continue
            return
        else:
            print(f"Draft {draft['id']} left unsent.")
            return


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("reindex")
    sp = sub.add_parser("search")
    sp.add_argument("query")
    sp.add_argument("--k", type=int, default=5)
    sp.add_argument("--sender")
    sp.add_argument("--after")
    sp.add_argument("--before")
    sub.add_parser("run")
    args = ap.parse_args()

    agent = EmailAgent()
    if args.cmd == "reindex":
        print(f"Indexed {agent.reindex()} emails.")
    elif args.cmd == "search":
        _print_results(agent.search_emails(args.query, args.k, sender=args.sender,
                                           after=args.after, before=args.before))
    else:
        interactive(agent)


if __name__ == "__main__":
    main()
