"""Synthetic support-ticket dataset for evaluating the triage/response agent.

Reference labels (expected_category, expected_escalate) are my best-guess
ground truth given the agent's rules — a couple of examples are deliberately
ambiguous or edge-case-y (see notes) because a realistic eval set should
surface real gaps, not just confirm easy wins.
"""
from dotenv import load_dotenv
from langsmith import Client

load_dotenv()

DATASET_NAME = "support-ticket-triage-eval"
DATASET_DESCRIPTION = (
    "Synthetic support tickets for evaluating the triage/response agent: "
    "category classification, escalation correctness, and response quality."
)

EXAMPLES = [
    {
        "ticket_text": "I was charged twice for my subscription this month and want a refund.",
        "expected_category": "billing",
        "expected_escalate": True,
    },
    {
        "ticket_text": "How do I update the credit card you have on file?",
        "expected_category": "billing",
        "expected_escalate": False,
    },
    {
        "ticket_text": "You charged me $15 twice this week, please refund the duplicate charge.",
        "expected_category": "billing",
        "expected_escalate": True,
    },
    {
        "ticket_text": "When does my subscription renew and how much will it cost?",
        "expected_category": "billing",
        "expected_escalate": False,
    },
    {
        "ticket_text": "This is unacceptable, I demand a $300 refund right now or I'm disputing the charge with my bank!",
        "expected_category": "billing",
        "expected_escalate": True,
    },
    {
        "ticket_text": "I cannot log into my account, it just spins forever.",
        "expected_category": "technical",
        "expected_escalate": False,
    },
    {
        "ticket_text": "The password reset link you sent says it doesn't work.",
        "expected_category": "technical",
        "expected_escalate": False,
    },
    {
        "ticket_text": "The app crashed when I tried to export my report, error code E4021.",
        "expected_category": "technical",
        "expected_escalate": False,
    },
    {
        "ticket_text": "Everything in the app is just really slow today.",
        "expected_category": "technical",
        "expected_escalate": False,
    },
    {
        "ticket_text": "My exported PDF has completely garbled fonts, never seen this before.",
        "expected_category": "technical",
        "expected_escalate": False,
        "note": "Not in the mock KB (only login/password/crash/slow) — tests behavior on a genuine KB miss.",
    },
    {
        "ticket_text": "Do you support dark mode in the app?",
        "expected_category": "general",
        "expected_escalate": False,
    },
    {
        "ticket_text": "Do you have an affiliate or referral program?",
        "expected_category": "general",
        "expected_escalate": False,
    },
    {
        "ticket_text": "I think my account was hacked — there are purchases I never made.",
        "expected_category": "technical",
        "expected_escalate": True,
        "note": (
            "Edge case: security/fraud-flavored, no literal 'refund' mention, "
            "so the current billing-refund escalation rule likely won't fire "
            "even though a human almost certainly should be looped in. "
            "Intentionally included to test for this gap."
        ),
    },
]


def build_dataset():
    client = Client()
    if client.has_dataset(dataset_name=DATASET_NAME):
        dataset = client.read_dataset(dataset_name=DATASET_NAME)
        print(
            f"Dataset '{DATASET_NAME}' already exists (id={dataset.id}); "
            "skipping example creation to avoid duplicates."
        )
        return dataset

    dataset = client.create_dataset(
        dataset_name=DATASET_NAME, description=DATASET_DESCRIPTION
    )
    client.create_examples(
        inputs=[{"ticket_text": e["ticket_text"]} for e in EXAMPLES],
        outputs=[
            {
                "expected_category": e["expected_category"],
                "expected_escalate": e["expected_escalate"],
            }
            for e in EXAMPLES
        ],
        dataset_id=dataset.id,
    )
    print(f"Created dataset '{DATASET_NAME}' with {len(EXAMPLES)} examples.")
    return dataset


if __name__ == "__main__":
    build_dataset()
