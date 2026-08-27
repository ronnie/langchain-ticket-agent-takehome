"""Run the SDK-side LangSmith evaluation experiment against the ticket agent."""
from dotenv import load_dotenv
from langsmith import evaluate

from dataset import DATASET_NAME
from evaluators import (
    category_correct,
    escalate_correct,
    response_quality,
    retry_count_metric,
)
from graph import run_ticket

load_dotenv()


def target(inputs: dict) -> dict:
    result = run_ticket(inputs["ticket_text"])
    return {
        "category": result["category"],
        "escalate": result["escalate"],
        "final_response": result["final_response"],
        "retry_count": result["retry_count"],
    }


if __name__ == "__main__":
    results = evaluate(
        target,
        data=DATASET_NAME,
        evaluators=[
            category_correct,
            escalate_correct,
            response_quality,
            retry_count_metric,
        ],
        experiment_prefix="ticket-agent-sdk",
        description="SDK-run evaluation of the support ticket triage agent.",
        max_concurrency=3,
    )
    print(results)
