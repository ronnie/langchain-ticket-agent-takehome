"""Support ticket triage & response agent.

Flow:
    classify_ticket
          |
          v (conditional edge on category)
    billing_node / technical_node / general_node
          |
          v
    draft_response <----------------+
          |                         |
          v                         | (loop: critique failed, retries left)
    critique_response ---(fail)-----+
          |
          v (pass, or retries exhausted)
    confidence_gate
          |
          v (conditional edge)
    auto_send  /  escalate_to_human
"""
import os
from typing import TypedDict

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, START, END

from tools import lookup_billing_policy, search_kb

load_dotenv()

MODEL_NAME = "claude-haiku-4-5-20251001"
MAX_RETRIES = 2
CATEGORIES = ("billing", "technical", "general")

llm = ChatAnthropic(model=MODEL_NAME, temperature=0)


class TicketState(TypedDict):
    ticket_text: str
    category: str
    specialist_notes: str
    draft: str
    critique_feedback: str
    critique_passed: bool
    retry_count: int
    escalate: bool
    final_response: str


def classify_ticket(state: TicketState) -> dict:
    prompt = (
        "Classify this support ticket into exactly one category: "
        "billing, technical, or general.\n"
        "Reply with only the single category word, nothing else.\n\n"
        f"Ticket: {state['ticket_text']}"
    )
    reply = llm.invoke(prompt).content.strip().lower()
    category = reply if reply in CATEGORIES else "general"
    return {"category": category}


def route_by_category(state: TicketState) -> str:
    return state["category"]


def billing_node(state: TicketState) -> dict:
    policy = lookup_billing_policy()
    return {"specialist_notes": f"Billing policy on file: {policy}"}


def technical_node(state: TicketState) -> dict:
    article = search_kb(state["ticket_text"])
    return {"specialist_notes": f"Relevant KB article: {article}"}


def general_node(state: TicketState) -> dict:
    return {
        "specialist_notes": (
            "No specialist system applies. Respond helpfully and, if the "
            "request is ambiguous, ask one clarifying question."
        )
    }


def draft_response(state: TicketState) -> dict:
    feedback_block = ""
    if state.get("critique_feedback"):
        feedback_block = (
            f"\n\nYour previous draft was rejected for this reason: "
            f"{state['critique_feedback']}\nFix that specific issue in this draft."
        )
    prompt = (
        "You are a support agent replying to a customer ticket. Write a short, "
        "direct reply (3-5 sentences). Ground your answer in the specialist "
        "notes below — don't invent policy details.\n\n"
        f"Ticket: {state['ticket_text']}\n"
        f"Category: {state['category']}\n"
        f"Specialist notes: {state['specialist_notes']}"
        f"{feedback_block}"
    )
    draft = llm.invoke(prompt).content.strip()
    return {"draft": draft, "retry_count": state.get("retry_count", 0)}


def critique_response(state: TicketState) -> dict:
    prompt = (
        "Grade this draft support reply against the ticket and specialist "
        "notes. Check: does it directly address the customer's ask, does it "
        "stay consistent with the specialist notes (no invented policy), and "
        "is the tone professional?\n\n"
        f"Ticket: {state['ticket_text']}\n"
        f"Specialist notes: {state['specialist_notes']}\n"
        f"Draft reply: {state['draft']}\n\n"
        "Respond in exactly this format:\n"
        "VERDICT: PASS or FAIL\n"
        "FEEDBACK: <one sentence, only needed if FAIL>"
    )
    reply = llm.invoke(prompt).content.strip()
    passed = "VERDICT: PASS" in reply.upper()
    feedback = ""
    if not passed:
        for line in reply.splitlines():
            if line.upper().startswith("FEEDBACK"):
                feedback = line.split(":", 1)[-1].strip()
    return {"critique_passed": passed, "critique_feedback": feedback}


def route_after_critique(state: TicketState) -> str:
    if not state["critique_passed"] and state.get("retry_count", 0) < MAX_RETRIES:
        return "retry"
    return "proceed"


def increment_retry(state: TicketState) -> dict:
    return {"retry_count": state.get("retry_count", 0) + 1}


def confidence_gate(state: TicketState) -> dict:
    ran_out_of_retries = (
        not state["critique_passed"] and state.get("retry_count", 0) >= MAX_RETRIES
    )
    if ran_out_of_retries:
        return {"escalate": True}

    prompt = (
        "Should this support ticket be escalated to a human before the reply "
        "below is sent? Escalate for: financial commitments (refunds, credits, "
        "chargebacks), security or fraud concerns (unauthorized access, "
        "compromised accounts), legal exposure, or anything the specialist "
        "notes don't clearly authorize the agent to resolve on its own. "
        "Don't escalate routine informational replies.\n"
        "Reply with only YES or NO.\n\n"
        f"Ticket: {state['ticket_text']}\n"
        f"Category: {state['category']}\n"
        f"Specialist notes: {state['specialist_notes']}\n"
        f"Proposed reply: {state['draft']}"
    )
    reply = llm.invoke(prompt).content.strip().upper()
    return {"escalate": reply.startswith("YES")}


def route_after_gate(state: TicketState) -> str:
    return "escalate" if state["escalate"] else "auto_send"


def auto_send(state: TicketState) -> dict:
    return {"final_response": state["draft"]}


def escalate_to_human(state: TicketState) -> dict:
    return {
        "final_response": (
            f"[ESCALATED FOR HUMAN REVIEW] Suggested reply: {state['draft']}"
        )
    }


def build_graph():
    graph = StateGraph(TicketState)

    graph.add_node("classify_ticket", classify_ticket)
    graph.add_node("billing_node", billing_node)
    graph.add_node("technical_node", technical_node)
    graph.add_node("general_node", general_node)
    graph.add_node("draft_response", draft_response)
    graph.add_node("critique_response", critique_response)
    graph.add_node("increment_retry", increment_retry)
    graph.add_node("confidence_gate", confidence_gate)
    graph.add_node("auto_send", auto_send)
    graph.add_node("escalate_to_human", escalate_to_human)

    graph.add_edge(START, "classify_ticket")
    graph.add_conditional_edges(
        "classify_ticket",
        route_by_category,
        {
            "billing": "billing_node",
            "technical": "technical_node",
            "general": "general_node",
        },
    )
    graph.add_edge("billing_node", "draft_response")
    graph.add_edge("technical_node", "draft_response")
    graph.add_edge("general_node", "draft_response")
    graph.add_edge("draft_response", "critique_response")
    graph.add_conditional_edges(
        "critique_response",
        route_after_critique,
        {"retry": "increment_retry", "proceed": "confidence_gate"},
    )
    graph.add_edge("increment_retry", "draft_response")
    graph.add_conditional_edges(
        "confidence_gate",
        route_after_gate,
        {"escalate": "escalate_to_human", "auto_send": "auto_send"},
    )
    graph.add_edge("auto_send", END)
    graph.add_edge("escalate_to_human", END)

    return graph.compile()


app = build_graph()


def run_ticket(ticket_text: str) -> TicketState:
    initial_state: TicketState = {
        "ticket_text": ticket_text,
        "category": "",
        "specialist_notes": "",
        "draft": "",
        "critique_feedback": "",
        "critique_passed": False,
        "retry_count": 0,
        "escalate": False,
        "final_response": "",
    }
    return app.invoke(initial_state)


if __name__ == "__main__":
    result = run_ticket(
        "I was charged twice for my subscription this month and want a refund."
    )
    print("Category:", result["category"])
    print("Retries:", result["retry_count"])
    print("Escalate:", result["escalate"])
    print("Final response:", result["final_response"])
