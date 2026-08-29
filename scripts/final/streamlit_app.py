from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

from langgraph_flow import DEFAULT_GITHUB_REPO, run_langgraph_workflow


def init_state() -> None:
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("last_state", None)


def render_plan(state_payload: dict) -> None:
    rows = [
        {
            "step": step["name"],
            "purpose": step["purpose"],
            "status": step["status"],
            "detail": step["detail"],
        }
        for step in state_payload.get("plan", [])
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_rag(state_payload: dict) -> None:
    rag_calls = state_payload.get("rag_calls", [])
    if not rag_calls:
        st.info("RAG was not called for this route.")
        return
    for call in rag_calls:
        st.write(f"Source: `{call['source']}` · Status: `{call['status']}` · Success: `{call['success']}`")
        if call.get("fallback_reason"):
            st.warning(call["fallback_reason"])
        if call.get("answer"):
            st.markdown(call["answer"])
        if call.get("citations"):
            st.write("Citations:", ", ".join(call["citations"]))
        with st.expander("Retrieved context"):
            st.json(call.get("retrieved_context_by_id") or {})


def render_tools(state_payload: dict) -> None:
    calls = state_payload.get("tool_calls", [])
    results = state_payload.get("external_tool_results", [])
    if not calls:
        st.info("No external tool was called.")
        return
    st.subheader("Tool requests")
    st.json(calls)
    st.subheader("Tool observations")
    st.json(results)


def render_synthesis(state_payload: dict) -> None:
    calls = state_payload.get("synthesis_calls", [])
    if not calls:
        st.info("Model synthesis was not called; final answer used deterministic fallback.")
        return
    st.json(calls)


def main() -> None:
    st.set_page_config(page_title="SuppBro Final", layout="wide")
    init_state()

    st.title("SuppBro Final LangGraph workflow")
    st.caption("Chat + trace dashboard for the route-aware support workflow.")

    with st.sidebar:
        st.header("Run settings")
        repo = st.text_input("GitHub repo", DEFAULT_GITHUB_REPO)
        issue_number_text = st.text_input("Issue number override", "")
        allow_external = st.checkbox("Allow Stack Overflow/community search", value=True)
        enable_rag = st.checkbox("Enable HW4 RAG", value=True)
        min_vector_score = st.slider("Min vector score", 0.0, 1.0, 0.30, 0.05)
        issue_number = int(issue_number_text) if issue_number_text.strip().isdigit() else None

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    question = st.chat_input("Ask about Debezium docs, issues, or community troubleshooting")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.spinner("Running LangGraph workflow..."):
            state_payload = run_langgraph_workflow(
                question,
                repo=repo,
                issue_number=issue_number,
                allow_external_community_search=allow_external,
                min_vector_score=min_vector_score,
                enable_rag=enable_rag,
            )
            st.session_state.last_state = state_payload

        st.session_state.messages.append({"role": "assistant", "content": state_payload["final_answer"]})
        with st.chat_message("assistant"):
            st.markdown(state_payload["final_answer"])

    state_payload = st.session_state.last_state
    if not state_payload:
        st.info("Run a chat question to see route, graph nodes, plan, observations, and current state.")
        return

    st.divider()
    left, right = st.columns([1, 2])
    with left:
        st.metric("Route", state_payload["selected_route"])
        st.metric("Current step", state_payload["current_step"])
        st.metric("Fallback used", str(state_payload["fallback_used"]))
        st.metric("Needs clarification", str(state_payload["requires_clarification"]))
    with right:
        st.write("Route reason")
        st.info(state_payload["route_reason"])
        st.write("Executed LangGraph nodes")
        st.code(" -> ".join(state_payload.get("executed_nodes", [])), language="text")

    tab_plan, tab_rag, tab_tools, tab_synthesis, tab_state = st.tabs(["Plan trace", "RAG", "Tools", "Synthesis", "State JSON"])
    with tab_plan:
        render_plan(state_payload)
        st.write("Observations")
        st.json(state_payload["observations"])
    with tab_rag:
        render_rag(state_payload)
    with tab_tools:
        render_tools(state_payload)
    with tab_synthesis:
        render_synthesis(state_payload)
    with tab_state:
        st.code(json.dumps(state_payload, indent=2, ensure_ascii=False), language="json")


if __name__ == "__main__":
    main()
