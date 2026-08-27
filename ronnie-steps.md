# LangChain Take-Home — Running Checklist

Live log of every setup/build/eval step, kept for the walkthrough call.
Each item: what we did, the exact command or UI path (with URL), and notes on what happened.
Appended to continuously as steps are completed — this file is the source for the walkthrough narration.

## Phase 0 — Environment Setup

- [x] Checked available Python — system Python 3.9.6 (`/usr/bin/python3`), no Homebrew/pyenv Python installed. Confirmed 3.9 is sufficient for LangGraph (no upgrade needed).
  ```bash
  python3 --version
  ```
- [x] Created project directory and virtual environment.
  ```bash
  mkdir -p ~/langchain-takehome && cd ~/langchain-takehome
  python3 -m venv venv
  ```
- [x] Installed LangGraph, LangSmith, LangChain, and the Anthropic integration.
  ```bash
  source venv/bin/activate
  pip install --upgrade pip
  pip install langgraph langsmith langchain langchain-anthropic python-dotenv
  ```
  Versions installed: `langgraph==0.6.11`, `langsmith==0.4.37`, `langchain==0.3.30`, `langchain-anthropic==0.3.22`.
- [x] Pinned dependencies to `requirements.txt`.
  ```bash
  pip freeze | grep -iE "^(langgraph|langsmith|langchain|anthropic|python-dotenv)" > requirements.txt
  ```
- [x] Created `.env.example` (template for API keys) and `.gitignore` (excludes `venv/`, `.env`).
- [x] Initialized a local git repo and committed scaffolding (`.gitignore`, `.env.example`, `requirements.txt`, this file). Not pushed anywhere yet — will ask before creating/pushing to a remote.
  ```bash
  git init
  git add .gitignore .env.example requirements.txt ronnie-steps.txt
  git commit -m "Initial project scaffolding"
  ```
- [ ] **Your action:** copy the template and fill in your real keys (never shared with Claude/committed to git):
  ```bash
  cd ~/langchain-takehome
  cp .env.example .env
  open -e .env   # or your editor of choice
  ```
  Fill in:
  - `ANTHROPIC_API_KEY` — from https://console.anthropic.com/settings/keys
  - `LANGSMITH_API_KEY` — from https://smith.langchain.com/settings (API Keys tab)
- [x] Wrote `smoke_test.py` — loads `.env`, checks both keys are present, makes one trivial `ChatAnthropic` call, prints the LangSmith project/tracing config.
- [ ] Ran smoke test — **failed**: keys are valid/loaded correctly, but the Anthropic API call returned `400 invalid_request_error: Your credit balance is too low to access the Anthropic API`.
  ```bash
  source venv/bin/activate
  python3 smoke_test.py
  ```
  Note for walkthrough: a Claude Pro subscription (claude.ai) is separate from Anthropic API billing (console.anthropic.com) — API calls need credits purchased there even with an active Pro plan. Waiting on credits to be added before retrying.
- [x] Re-ran smoke test after adding API credits — **passed**. Model replied "Hello", tracing enabled, project = `ronnie-ticket-agent-takehome`.
  ```bash
  source venv/bin/activate
  python3 smoke_test.py
  ```
- [x] Verified traces landed in the LangSmith UI.
  UI path: https://smith.langchain.com → **Tracing** → project **`ronnie-ticket-agent-takehome`**
  Saw both smoke-test runs listed: the failed attempt (`BadRequestError`, $0.00, before credits were added) and the successful one (`ai: Hello`, 18 tokens, $0.000034, 0.94s latency). Confirms tracing is wired correctly end to end before writing any real agent code.
  (Used the in-app Browser at first — wasn't logged into the account there; switched to Claude in Chrome, which had an active logged-in session, to actually view it.)
  Cross-checked independently: Ronnie also pulled up the same project URL in his own browser and confirmed the identical two traces — good corroborating evidence for the walkthrough.
  Screenshot saved to repo: `evidence/langsmith-smoke-test-traces.png` (copied from `~/Screenshots/`; hit a filename gotcha — macOS screenshot names use a narrow no-break space (U+202F) before "PM", not a regular space, so a plain shell `cp` with a normal space couldn't find the file until resolved via Python's `os.listdir`).

## Phase 1 — Build the LangGraph Agent

- [x] Designed the graph: `classify_ticket` -> conditional route to `billing_node` / `technical_node` / `general_node` -> `draft_response` -> `critique_response` -> (loop back to `draft_response` via `increment_retry`, up to 2 retries, if critique fails) -> `confidence_gate` -> conditional route to `auto_send` / `escalate_to_human`.
- [x] Wrote `tools.py` — two small mock lookups (`lookup_billing_policy`, `search_kb`) that specialist nodes call, so responses are grounded in something concrete instead of the raw ticket alone.
- [x] Wrote `graph.py` — full `StateGraph` implementation: `TicketState` TypedDict, all nodes, both conditional edges (route-by-category and route-after-critique, plus route-after-gate), compiled app, and a `run_ticket()` helper for manual testing. Uses `claude-haiku-4-5-20251001` for every LLM node (cheap/fast, sufficient for this exercise).
  Escalation rule (deterministic, not LLM-judged): escalate if retries are exhausted and critique still fails, OR if it's a billing ticket whose draft mentions a refund (policy-sensitive, needs human sign-off per the mock billing policy).
- [x] Manually ran the full graph on 4 sample tickets to sanity-check every branch:
  ```bash
  python3 graph.py   # billing/refund ticket -> correctly escalated
  python3 -c "from graph import run_ticket; ..."   # login (technical), dark mode (general), crash w/ error code (technical)
  ```
  All 4 classified correctly and produced sensible drafts; all passed critique on the first attempt (retry_count stayed 0), so the loop itself wasn't exercised by these easy cases.
- [x] Targeted test of `critique_response` in isolation with a deliberately policy-violating draft ("I'll refund your $500 immediately, no approval needed") — correctly returned `critique_passed: False` with specific feedback ("violates specialist notes... requires manager review for refunds over $100"). Confirms the retry-loop logic is sound; the eval dataset (Phase 2) should include a few tickets tricky enough to trigger it end-to-end for real.

## Phase 2 — Build the Dataset

- [x] Wrote `dataset.py` — 13 synthetic support tickets (5 billing, 5 technical, 2 general, 1 security-flavored edge case) with reference labels (`expected_category`, `expected_escalate`). Deliberately included two edge cases rather than only easy wins:
  - A ticket with no KB match ("garbled fonts" export issue) — tests behavior on a genuine knowledge-base miss.
  - An account-hacked/fraud ticket with no literal "refund" mention — the current escalation rule (billing + "refund" keyword) likely won't catch this even though it probably should escalate. Included on purpose to see if the eval surfaces the gap.
- [x] Created the dataset in LangSmith via the **SDK** (`client.create_dataset` + `client.create_examples`), idempotent — reruns skip creation if it already exists.
  ```bash
  source venv/bin/activate
  python3 dataset.py
  ```
  Output: `Created dataset 'support-ticket-triage-eval' with 13 examples.`
  UI path to view it: https://smith.langchain.com → **Datasets & Experiments** → `support-ticket-triage-eval`

## Phase 3 — Evaluators

- [x] Wrote `evaluators.py` — 4 evaluators matching what the take-home calls out (correctness, helpfulness) plus one operational metric:
  - `category_correct` — exact-match vs. `expected_category`
  - `escalate_correct` — exact-match vs. `expected_escalate`
  - `response_quality` — LLM-as-judge (Claude Haiku), 1-5 helpfulness/professionalism score
  - `retry_count_metric` — not correctness, just logs how many times the draft->critique loop fired per example

## Phase 4 — Run Evaluation (SDK)

- [x] Wrote `run_eval_sdk.py` — wraps `run_ticket()` as the `target` function, calls `langsmith.evaluate()` against the `support-ticket-triage-eval` dataset with all 4 evaluators.
  ```bash
  source venv/bin/activate
  python3 run_eval_sdk.py
  ```
  Experiment: `ticket-agent-sdk-b84b88ac`
  Results URL: https://smith.langchain.com/o/56b01680-1dc0-4312-9b3a-27f81896b348/datasets/e1d3348d-8463-47e8-9ff0-6c4f846971a2/compare?selectedSessions=188462e4-e677-4441-b917-4dce805a4a9e
- [x] Reviewed results in the LangSmith UI. (Note: couldn't auto-save this screenshot to the repo the way the first one worked — Claude in Chrome's `save_to_disk` path isn't reachable from the project shell. Grab a live screenshot of the compare view above during the walkthrough call instead, or paste one in like before and I'll place it in `evidence/`.)
  **Aggregate scores (13 examples):** category_correct 0.88 avg (11/13) · escalate_correct 1.00 avg (13/13) · response_quality 4.25/5 avg · retry_count 0.00 avg · total cost $0.0113.
  **Key finding — row 3, the intentional edge case** ("I think my account was hacked — there are purchases I never made"): I'd labeled this `expected_category: technical`, expecting the agent's billing-only escalation rule to miss it (no literal "refund" keyword in the ticket). What actually happened: the agent classified it as **billing** (arguably reasonable — it's about unauthorized charges), drafted a reply that itself proposed a refund as part of resolving the issue, and the refund-keyword rule fired on that generated text — so it escalated correctly, but for a coincidental reason, not a deliberate security-escalation rule. Confirmed by rerunning the ticket locally: `draft` contains "I can process a full refund immediately" → `"refund" in draft.lower()` → `True`.
  **Design smell this surfaces:** gating escalation on a keyword match against LLM-generated free text is brittle — it happened to work here, but a differently-phrased draft (or a model swap) could just as easily not mention "refund" and silently skip escalation on a security-sensitive ticket. A cleaner design would classify escalation as its own explicit signal, not an accidental byproduct of draft wording. Worth calling out on the walkthrough as a "what I learned" moment.
  **Other observation:** retry_count was 0 across all 13 examples — the critique loop, though verified working in isolation (Phase 1), never fired on this dataset because the draft prompt already conditions tightly on the specialist notes. Says more about this dataset being too "easy" for the agent than about the loop being pointless — a meaningfully adversarial eval set would need cases designed to provoke a bad first draft.
  **Minor:** one row (the affiliate-program question) had a latency spike to 10.75s vs. ~3s typical — not investigated further, likely just API jitter, but worth a mention as a "things I'd keep an eye on" item.

## Phase 5 — Run Evaluation (UI)

Note going in: cleanly UI-evaluating a whole custom multi-node LangGraph app isn't really a supported flow — the Playground is built around a single prompt+model, not an arbitrary graph. LangSmith's own "+ Experiment" menu on the dataset page confirms this split, offering exactly three UI-adjacent options: **Run in Playground** (single prompt), **Run in LangSmith Studio** (for a deployed LangGraph app — more infra than this exercise needs), and **Run in SDK**. Went with Playground, running a single-prompt version of the `classify_ticket` step (the most naturally single-prompt piece of the pipeline) rather than pretending the whole graph fits.

- [x] From the dataset page, **+ Experiment → Run in Playground**.
  UI path: https://smith.langchain.com → **Datasets & Experiments** → `support-ticket-triage-eval` → **+ Experiment** → **Run in Playground**
- [x] Configured the Playground run to mirror `classify_ticket`:
  - System prompt: "Classify this support ticket into exactly one category: billing, technical, or general. Reply with only the single category word, nothing else."
  - Human message: `{ticket_text}` (auto-mapped to the dataset's input column)
  - Model: switched Provider from the OpenAI default to **Anthropic**, model `claude-haiku-4-5-20251001` (typed in manually — not in the visible preset list, but accepted)
- [x] Added an evaluator via **+ Evaluator → Correctness** (prebuilt LLM-as-judge, "whether an answer semantically matches reference").
  - Had to reconfigure its judge model too: it defaulted to a different provider (OpenAI) than the main prompt, which would have needed a separate `OPENAI_API_KEY`. Switched it to Anthropic (`claude-sonnet-5`) instead — see Friction Log entry #3, this requires entering the Anthropic key into LangSmith's own **Secrets & API keys** store (separate from local `.env`). **Ronnie entered his key directly into that LangSmith UI field** — Claude does not enter API keys into forms under any circumstances, so this one step was handed off.
- [x] Clicked **Start**. Ran all 13 examples through Claude Haiku with live per-row outputs and correctness scores.
- [x] **Found a real evaluator bug** (Friction Log entry #2): the Correctness evaluator's scores didn't track actual correctness — e.g. 4 exact category matches (technical==technical, billing==billing) scored 0.00 while 2 matches of the same kind scored 1.00. Opened the trace for one 0.00 row and found the judge's own reasoning concluded *"the output can be considered correct"*, immediately followed by unparsed leaked text: `</comment> <parameter name="correctness">true`. The judge said correct; the system recorded incorrect. Looks like a structured-output parsing bug specific to non-OpenAI judge models.
  UI path to reproduce: open the experiment → click any row → **Feedback** tab → click the `correctness` comment to expand full reasoning.
- [x] Logged both new findings in `FRICTION-LOG.md` (entries #2 and #3).

## Phase 6 — Debug & Iterate

- [x] **Fixed the escalation design flaw** found in Phase 4/5 (the "hacked account" ticket only escalated by coincidence, via a brittle `"refund" in draft.lower()` keyword check). Replaced `confidence_gate` in `graph.py` with an explicit LLM judgment call: given the ticket, category, specialist notes, and proposed reply, ask "should this be escalated to a human?" with instructions covering financial commitments, security/fraud, legal exposure, and anything outside what the specialist notes authorize. Kept the deterministic "retries exhausted" rule as-is (that one was always sound).
- [x] Re-tested the hacked-account ticket directly — still escalates (`True`), now because the model explicitly reasons about the security/fraud angle, not because its draft happened to contain the word "refund."
  ```bash
  python3 -c "from graph import run_ticket; ..."
  ```
- [x] Reran the full SDK evaluation to check for regressions.
  ```bash
  python3 run_eval_sdk.py
  ```
  Experiment: `ticket-agent-sdk-8a7b3e1c`
  Results URL: https://smith.langchain.com/o/56b01680-1dc0-4312-9b3a-27f81896b348/datasets/e1d3348d-8463-47e8-9ff0-6c4f846971a2/compare?selectedSessions=3347a9a8-6dd8-4564-add9-83edd549524a
  **Per-row results (13/13):** 12/13 category matches (row 3, the hacked-account ticket, still labeled "technical" in my reference but the agent still says "billing" — a genuinely debatable call either way, not a regression). 12/13 escalate matches by exact-match-to-reference — **but the one "miss" is actually the more interesting finding, not a bug:**
  **Row 11** ("You charged me $15 twice this week, please refund the duplicate charge") no longer escalates. Previously it did, purely because the old rule matched on "refund." Under the new LLM judgment, it correctly does *not* escalate — and checking it against my own mock billing policy ("full refunds within 30 days, no questions asked... refunds over $100 or 30+ days require approval"), $15 is squarely within the no-escalation-needed range. **My reference label (`expected_escalate: true`) was itself wrong** — I wrote it with the same "any refund mention = escalate" assumption baked into the original buggy rule, so the flawed rule and the flawed ground truth matched each other by construction. Fixing the agent's logic surfaced a flaw in my eval dataset, not just in the agent. Lesson for the walkthrough: reference labels written by the same person who wrote the system logic are a weak check — they can encode the same blind spot twice.
  **Trade-off noted:** the fix costs one extra LLM call per ticket. Median latency went from 3.03s to 3.71s and total cost from $0.0113 to $0.0186 across the 13-example run. Worth it here for correctness, but a real product decision (cost/latency vs. reliability) worth calling out explicitly rather than treating as free.
  **Minor UI oddity, not chased further:** the aggregate "AVG" figures shown at the top of the compare view (e.g., `category_correct 1.00 AVG`) didn't match what a manual count of the per-row values gives (12/13 ≈ 0.92). Low-confidence guess: a stale/partial render of the summary stat rather than a real scoring issue, since the per-row numbers and the underlying trace data were internally consistent. Flagging as a "noticed but didn't root-cause" item rather than adding it to the friction log as a confirmed bug.
- [x] **Corrected the bad reference label** — updated both `dataset.py` (source of truth) and the live LangSmith dataset via SDK (`client.update_example`) so the $15 duplicate-charge ticket's `expected_escalate` is `False`, matching the actual policy.
  ```bash
  python3 -c "from langsmith import Client; ... client.update_example(example_id=..., outputs={'expected_category': 'billing', 'expected_escalate': False})"
  ```
  UI path to verify: https://smith.langchain.com → dataset `support-ticket-triage-eval` → **Examples** tab → find the $15 example.

## Wrap-up

- [x] Wrote `README.md` — project overview, architecture diagram, file guide, setup/run instructions, latest eval summary.
- [x] Created a private GitHub repo and pushed everything.
  ```bash
  gh repo create langchain-ticket-agent-takehome --private --source=. --remote=origin --push
  ```
  Repo: https://github.com/ronnie/langchain-ticket-agent-takehome (private — flip to public with `gh repo edit langchain-ticket-agent-takehome --visibility public`, or add the interviewer as a collaborator, whichever's preferred before sharing the link)

## Phase 7 — Friction Log
See `FRICTION-LOG.md` (created and updated live as issues come up).
- [x] Entry #1 logged: funded LLM provider API access is a silent prerequisite — a Claude Pro subscription doesn't cover API billing, and neither the take-home prompt nor the linked docs flag this. Caused the first agent call to fail with an unclear-to-newcomers 400 error.
- [x] Entry #2 logged (found during Phase 5): the prebuilt "Correctness" LLM-as-judge evaluator scores inconsistently when run with an Anthropic judge model — exact category matches scored both 0.00 and 1.00 with no discernible pattern, and one trace showed the judge's own reasoning conclude "the output can be considered correct" while the recorded score was 0.00, with raw unparsed tool-call text (`</comment> <parameter name="correctness">true`) leaking into the comment field. Looks like a structured-output parsing bug specific to non-OpenAI judge models.
- [x] Entry #3 logged (found during Phase 5): UI-configured evaluators need their provider API key registered separately in LangSmith's own "Secrets & API keys" store, distinct from the local `.env` the SDK path reads from — not explained at the point you hit it.
