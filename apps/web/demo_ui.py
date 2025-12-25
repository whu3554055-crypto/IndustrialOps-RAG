"""Gradio 业务演示 UI — 调用 Gateway /v1/chat 与 /v1/feedback.

启动：GATEWAY_URL=http://localhost:8080 python apps/web/demo_ui.py
学习文档：docs/m7_demo.md §6
"""

from __future__ import annotations

import os

import gradio as gr
import httpx

GATEWAY = os.environ.get("GATEWAY_URL", "http://localhost:8080").rstrip("/")
SESSION = os.environ.get("DEMO_SESSION_ID", "business-demo")


def _chat(query: str, history: list[tuple[str, str]]) -> tuple[list[tuple[str, str]], str, str]:
    if not query.strip():
        return history, "", ""
    body = {"session_id": SESSION, "query": query.strip()}
    try:
        with httpx.Client(timeout=120.0) as client:
            r = client.post(f"{GATEWAY}/v1/chat", json=body)
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        err = f"[Gateway 不可用] {exc}"
        history = history + [(query, err)]
        return history, "", ""
    answer = data.get("answer", "")
    msg_id = data.get("message_id") or data.get("retrieval_log_id") or ""
    cites = data.get("citations") or []
    cite_txt = "\n".join(
        f"- {c.get('title', c.get('source_file', ''))} ({c.get('source_file', '')})"
        for c in cites[:5]
    )
    if cite_txt:
        answer = f"{answer}\n\n**引用：**\n{cite_txt}"
    history = history + [(query, answer)]
    return history, "", msg_id


def _send_feedback(message_id: str, rating: int, comment: str) -> str:
    if not message_id:
        return "请先提问并收到回答后再反馈。"
    payload = {
        "session_id": SESSION,
        "message_id": message_id,
        "rating": rating,
        "comment": comment or None,
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(f"{GATEWAY}/v1/feedback", json=payload)
            r.raise_for_status()
            return f"已记录反馈（rating={rating}）"
    except Exception as exc:
        return f"反馈失败: {exc}"


def build_ui() -> gr.Blocks:
    state_msg = gr.State("")
    with gr.Blocks(title="IndustrialOps-RAG 演示") as demo:
        gr.Markdown(
            "## 工业运维知识库演示\n"
            "语料为 **脱敏虚构** 设备文档。需 Gateway +（可选）vLLM 就绪。"
        )
        chatbot = gr.Chatbot(label="问答")
        with gr.Row():
            query = gr.Textbox(label="问题", placeholder="例如：P-101 出口压力正常范围？")
            send = gr.Button("发送", variant="primary")
        message_id = gr.Textbox(label="message_id（自动）", interactive=False)
        with gr.Row():
            up = gr.Button("👍 有帮助")
            down = gr.Button("👎 需改进")
        comment = gr.Textbox(label="补充说明（可选）")
        fb_status = gr.Markdown()

        send.click(
            _chat,
            inputs=[query, chatbot],
            outputs=[chatbot, query, message_id],
        )
        query.submit(
            _chat,
            inputs=[query, chatbot],
            outputs=[chatbot, query, message_id],
        )
        up.click(
            lambda mid, c: _send_feedback(mid, 1, c),
            inputs=[message_id, comment],
            outputs=fb_status,
        )
        down.click(
            lambda mid, c: _send_feedback(mid, -1, c),
            inputs=[message_id, comment],
            outputs=fb_status,
        )
    return demo


def main() -> None:
    ui = build_ui()
    ui.launch(server_name="0.0.0.0", server_port=int(os.environ.get("GRADIO_PORT", "7860")))


if __name__ == "__main__":
    main()
