"""Gradio UI for the Email Search & Drafting Agent.

    python app.py              # uses Ollama (nomic-embed-text + llama3.1)
    python app.py --offline    # no Ollama needed (keyword-ish search, template drafts)
    python app.py --share      # temporary public link (use only with the fake demo data)
"""
import argparse
import os


def _bypass_proxy_for_localhost():
    """Gradio checks http://127.0.0.1 is reachable; a system proxy/VPN can break that check."""
    hosts = "127.0.0.1,localhost,::1"
    for var in ("NO_PROXY", "no_proxy"):
        cur = os.environ.get(var, "")
        os.environ[var] = f"{cur},{hosts}" if cur else hosts


def build_ui(logic):
    import gradio as gr

    # Gradio 6 moved `theme` from Blocks() to launch(); support both.
    major = int(gr.__version__.split(".")[0])
    blocks_kwargs = {} if major >= 6 else {"theme": gr.themes.Soft()}
    launch_kwargs = {"theme": gr.themes.Soft()} if major >= 6 else {}

    with gr.Blocks(title="Email Search & Drafting Agent", **blocks_kwargs) as demo:
        gr.Markdown(
            "# Email Search & Drafting Agent\n"
            "Find an old email by meaning, read the thread, draft a reply, and send only after you "
            "type the confirmation phrase. *All emails here are fake demo data.*"
        )
        status_md = gr.Markdown(logic.status())

        email_state = gr.State(None)
        draft_state = gr.State(None)

        with gr.Tab("1. Find and reply"):
            with gr.Row():
                # ---------------- left: search ----------------
                with gr.Column(scale=4):
                    gr.Markdown("### Search")
                    query = gr.Textbox(label="What are you looking for?", lines=2,
                                       placeholder="e.g. the vendor quote for hosting that expires in June")
                    with gr.Row():
                        sender = gr.Textbox(label="From contains (optional)", placeholder="priya")
                        k = gr.Slider(1, 10, value=5, step=1, label="Max results")
                    with gr.Row():
                        after = gr.Textbox(label="After (YYYY-MM-DD)", placeholder="2026-05-01")
                        before = gr.Textbox(label="Before (YYYY-MM-DD)", placeholder="2026-09-30")
                    search_btn = gr.Button("Search", variant="primary")
                    gr.Examples(
                        examples=[
                            ["discount offered if we commit to 24 months"],
                            ["somebody was charged twice on an invoice"],
                            ["invitation to give a talk at a conference"],
                            ["hosting quotation expiring soon"],
                            ["bug where results appear duplicated"],
                            ["security problems that need fixing by end of June"],
                            ["when is my flight to Delhi"],
                        ],
                        inputs=[query], label="Try an example",
                    )
                    search_msg = gr.Markdown()
                    results = gr.Radio(choices=[], label="Results (select one)", interactive=True)

                # ---------------- right: thread + draft ----------------
                with gr.Column(scale=6):
                    gr.Markdown("### Thread")
                    summary_md = gr.Markdown("*Select a result to see its summary.*")
                    with gr.Accordion("Full thread", open=False):
                        thread_md = gr.Markdown()

                    gr.Markdown("### Draft a reply")
                    intent = gr.Textbox(label="What should the reply say or achieve?", lines=2,
                                        placeholder="e.g. Accept, and ask what the honorarium is")
                    gen_btn = gr.Button("Generate draft", variant="primary")
                    draft_msg = gr.Markdown()
                    to_box = gr.Textbox(label="To", interactive=False)
                    subject_box = gr.Textbox(label="Subject", interactive=False)
                    body_box = gr.Textbox(label="Body (editable)", lines=10, interactive=True)
                    save_btn = gr.Button("Save edits")

                    gr.Markdown("### Send (needs your explicit confirmation)")
                    phrase_md = gr.Markdown("*Generate a draft to get the confirmation phrase.*")
                    confirm_box = gr.Textbox(label="Type the confirmation phrase exactly",
                                             placeholder="SEND d_xxxxxxxx")
                    send_btn = gr.Button("Send", variant="stop")
                    send_msg = gr.Markdown()

        with gr.Tab("Drafts and sent"):
            drafts_df = gr.Dataframe(headers=["Draft", "Status", "To", "Subject", "Time"],
                                     value=logic.drafts_rows(), interactive=False, wrap=True)
            refresh_btn = gr.Button("Refresh")

        with gr.Tab("Mailbox (fake data)"):
            gr.Dataframe(headers=["ID", "Date", "From", "Subject", "Thread"],
                         value=logic.mailbox_rows(), interactive=False, wrap=True)

        with gr.Tab("Admin"):
            with gr.Row():
                reindex_btn = gr.Button("Rebuild index")
                reset_btn = gr.Button("Reset demo (clear drafts)")
            admin_msg = gr.Markdown()

        # ---------------- events ----------------
        def do_search(q, s, a, b, kk):
            choices, msg = logic.search(q, s, a, b, kk)
            return gr.update(choices=choices, value=None), msg

        def do_select(email_id):
            if not email_id:
                return None, "*Select a result to see its summary.*", "", None, "", "", "", "", ""
            thread, summary = logic.open_email(email_id)
            return email_id, summary, thread, None, "", "", "", "", "*Generate a draft to get the confirmation phrase.*"

        def do_draft(email_id, text):
            draft, msg = logic.make_draft(email_id, text)
            if not draft:
                return None, "", "", "", msg, gr.update()
            phrase = logic.required_phrase(draft["id"])
            return (draft["id"], draft["to"], draft["subject"], draft["body"], msg,
                    f"To send, type exactly: `{phrase}`")

        def do_send(draft_id, typed):
            return logic.send(draft_id, typed), logic.drafts_rows()

        search_btn.click(do_search, [query, sender, after, before, k], [results, search_msg])
        query.submit(do_search, [query, sender, after, before, k], [results, search_msg])
        results.change(do_select, [results],
                       [email_state, summary_md, thread_md, draft_state, to_box, subject_box, body_box,
                        send_msg, phrase_md])
        gen_btn.click(do_draft, [email_state, intent],
                      [draft_state, to_box, subject_box, body_box, draft_msg, phrase_md])
        save_btn.click(lambda d, b: logic.save_draft(d, b), [draft_state, body_box], [draft_msg])
        send_btn.click(do_send, [draft_state, confirm_box], [send_msg, drafts_df])
        refresh_btn.click(logic.drafts_rows, None, [drafts_df])
        reindex_btn.click(lambda: (logic.reindex(), logic.status()), None, [admin_msg, status_md])
        reset_btn.click(lambda: (logic.reset_demo(), logic.drafts_rows()), None, [admin_msg, drafts_df])

    return demo, launch_kwargs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="no Ollama: hash embeddings + template drafts")
    ap.add_argument("--port", type=int, default=7860)
    ap.add_argument("--share", action="store_true")
    args = ap.parse_args()

    if args.offline:  # must be set before config is imported
        os.environ["EMBED_BACKEND"] = "hash"
        os.environ["LLM_BACKEND"] = "extractive"

    _bypass_proxy_for_localhost()

    from ui_logic import DemoLogic  # imported after env vars are set

    demo, launch_kwargs = build_ui(DemoLogic())
    demo.launch(server_name="127.0.0.1", server_port=args.port, share=args.share, **launch_kwargs)


if __name__ == "__main__":
    main()