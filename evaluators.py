"""Evaluators for the support-ticket triage agent.

Three kinds of signal, matching what the take-home explicitly calls out
(correctness, helpfulness) plus one operational metric of my own:
  1. category_correct   - exact-match against the reference label
  2. escalate_correct   - exact-match against the reference label
  3. response_quality   - LLM-as-judge, 1-5 helpfulness/professionalism score
  4. retry_count_metric - not a "correctness" score, just logs how many times
                           the draft->critique loop fired, so we can see how
                           often self-correction actually kicks in
"""
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

load_dotenv()

JUDGE_MODEL = "claude-haiku-4-5-20251001"
judge_llm = ChatAnthropic(model=JUDGE_MODEL, temperature=0)


def category_correct(outputs: dict, reference_outputs: dict) -> dict:
    score = outputs.get("category") == reference_outputs.get("expected_category")
    return {"key": "category_correct", "score": score}


def escalate_correct(outputs: dict, reference_outputs: dict) -> dict:
    score = outputs.get("escalate") == reference_outputs.get("expected_escalate")
    return {"key": "escalate_correct", "score": score}


def response_quality(inputs: dict, outputs: dict) -> dict:
    prompt = (
        "Rate this support agent's reply to the customer ticket on a 1-5 scale:\n"
        "5 = directly resolves or clearly progresses the issue, professional tone\n"
        "3 = adequate but generic, or misses part of the ask\n"
        "1 = unhelpful, off-topic, or unprofessional\n"
        "Reply with only the digit.\n\n"
        f"Ticket: {inputs['ticket_text']}\n"
        f"Reply: {outputs.get('final_response', '')}"
    )
    raw = judge_llm.invoke(prompt).content.strip()
    try:
        score = int(raw[0])
    except (ValueError, IndexError):
        score = None
    return {"key": "response_quality", "score": score}


def retry_count_metric(outputs: dict) -> dict:
    return {"key": "retry_count", "score": outputs.get("retry_count", 0)}
