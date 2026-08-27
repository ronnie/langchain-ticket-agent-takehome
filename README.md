# Support Ticket Triage Agent

A LangGraph agent that classifies incoming support tickets, drafts a reply, critiques and
revises its own draft, and decides whether the reply is safe to auto-send or needs a human
in the loop — built as a take-home for a LangChain Technical Support Engineer application.

## What it does

```
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
confidence_gate  (LLM judgment: does this need a human before sending?)
      |
      v
 auto_send  /  escalate_to_human
```

- **`classify_ticket`** — routes the ticket into `billing`, `technical`, or `general`.
- **`billing_node` / `technical_node` / `general_node`** — each pulls in grounding context
  (a mock billing policy or a mock KB lookup, see `tools.py`) before drafting.
- **`draft_response` → `critique_response`** — a self-correction loop. The critique node
  grades the draft against the specialist notes and the ticket; a failing draft loops back
  with specific feedback, up to 2 retries.
- **`confidence_gate`** — decides escalation via an explicit LLM judgment (financial
  commitments, security/fraud, legal exposure, or anything the specialist notes don't
  clearly authorize), not a keyword heuristic — see `ronnie-steps.txt` Phase 6 for why that
  distinction matters.

## Files

| File | Purpose |
|---|---|
| `graph.py` | The LangGraph agent itself (state, nodes, edges) |
| `tools.py` | Mock billing-policy / KB lookups the specialist nodes call |
| `dataset.py` | Builds the 13-example synthetic eval dataset in LangSmith |
| `evaluators.py` | Custom evaluators: category correctness, escalation correctness, LLM-judge response quality, retry-count metric |
| `run_eval_sdk.py` | Runs the SDK-side LangSmith evaluation experiment |
| `smoke_test.py` | One-off script to confirm API keys + LangSmith tracing work |
| `ronnie-steps.txt` | **Full running log** of every setup/build/eval step, with exact commands and UI paths — the source of truth for the walkthrough |
| `FRICTION-LOG.md` | Three concrete LangGraph/LangSmith friction points found while building this, with repro steps and suggested fixes |

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in ANTHROPIC_API_KEY and LANGSMITH_API_KEY
python3 smoke_test.py  # confirms keys + tracing work
```

## Running it

```bash
python3 graph.py               # run one sample ticket through the agent
python3 dataset.py             # create/refresh the LangSmith eval dataset
python3 run_eval_sdk.py        # run the SDK-side evaluation experiment
```

The UI-side evaluation (Playground run + prebuilt "Correctness" evaluator) was run directly
in the LangSmith UI — see `ronnie-steps.txt` Phase 5 for the exact steps to reproduce it.

## Eval results (latest run)

13 synthetic tickets, evaluated on category correctness, escalation correctness, and
LLM-judged response quality:

- Category correct: 12/13 (the one miss is a genuinely debatable edge case — an
  account-hacked ticket that could reasonably be "billing" or "technical")
- Escalation correct: 12/13 against corrected reference labels
- Response quality: 4.75/5 average (LLM-as-judge)
- Full detail, including a bug found in LangSmith's prebuilt evaluator and a fix applied to
  the agent's own escalation logic mid-project, in `ronnie-steps.txt` (Phases 4–6) and
  `FRICTION-LOG.md`.
