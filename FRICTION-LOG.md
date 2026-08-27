# Friction Log

Things that were unclear, buggy, or unintuitive while doing this exercise — the kind of stuff I'd flag to the team if I were already on the job. Logged as they happened, in order.

---

### 1. Funded LLM provider access is a silent prerequisite

**What happened:** Set up `.env` with a valid Anthropic API key and a valid LangSmith API key, wired up tracing, and the very first agent call failed:
```
anthropic.BadRequestError: Error code: 400 - Your credit balance is too low to access the Anthropic API.
```
The key itself was valid — a Claude Pro (claude.ai) subscription just doesn't carry over to API billing, which is a separate balance at console.anthropic.com. Had to go add credits there before anything would run.

**Why it's friction:** Nothing in the take-home prompt, or in the LangGraph/LangSmith docs it links to, flags that you need *funded* LLM API access as a prerequisite, separate from whatever consumer subscription you might already have. The failure mode (a 400 from deep inside a LangChain stack trace) doesn't make the fix obvious to someone new to the ecosystem — you have to already know Anthropic splits Pro and API billing to diagnose it quickly.

**Suggested fix:** A one-line "before you start" prerequisite in onboarding docs / quickstarts: *"You'll need a funded API key from an LLM provider (this is separate from any consumer/Pro subscription to that provider) plus a LangSmith API key."* Cheap to add, saves a first-time user a confusing stall right at the starting line.

---

### 2. Prebuilt "Correctness" evaluator, run with an Anthropic judge, scores inconsistently — and its own reasoning contradicts its own score

**What happened:** Ran a UI-based experiment in the Playground: a simple ticket-classification prompt (Claude Haiku) over the `support-ticket-triage-eval` dataset, scored by LangSmith's prebuilt "Correctness" LLM-as-judge evaluator, reconfigured to use Claude Sonnet as the judge model (the default judge was GPT, which would've needed a separate OpenAI key just for this one evaluator — see below).

The scores made no sense against the actual outputs:

| Row | Ticket | Output | Reference | Correctness score |
|---|---|---|---|---|
| 1 | subscription renewal question | `billing` | `billing` | **0.00** |
| 2 | garbled PDF fonts | `technical` | `technical` | **1.00** |
| 4 | password reset link | `technical` | `technical` | **0.00** |
| 5 | can't log in | `technical` | `technical` | **0.00** |
| 6 | export crash, error code | `technical` | `technical` | **0.00** |
| 7 | affiliate program | `general` | `general` | **1.00** |

Four exact category matches scored 0.00 while two (of the same kind of match) scored 1.00 — no discernible pattern tied to actual correctness.

Opened the trace for row 4 to see the judge's actual reasoning (LangSmith UI: **Tracing** → click into the row → **Feedback** → click the `correctness` comment to expand). The judge's own written conclusion was: *"...the output can be considered correct."* — followed immediately by raw, unparsed text: `</comment> <parameter name="correctness">true`. That looks like leaked tool-call/XML formatting that never got parsed into the actual boolean score — so the judge said "correct" and the system recorded "incorrect" anyway.

**Why it's friction:** This isn't a judgment call or an ambiguous rubric edge case — the judge's stated reasoning and the recorded score directly contradict each other, and it happened repeatedly, not once. It strongly suggests the prebuilt evaluator's structured-output parsing was built and tested against an OpenAI-style function-calling response and doesn't reliably handle Claude's tool-use output format. A user who didn't dig into the per-row trace (which most people evaluating "am I getting a good score" wouldn't) would just see a bad aggregate correctness number and conclude their *agent* was wrong, when the *evaluator* was the broken part.

**Suggested fix:** Either fix the parsing so it's provider-agnostic, or — at minimum — surface a visible warning in the Playground when a judge model from a non-default provider is selected for a prebuilt evaluator, since the rubric/parsing may not have been validated against it.

---

### 3. UI-configured evaluators need a second, separate API key store

**What happened:** Configuring the same "Correctness" evaluator to use an Anthropic judge model required entering an `ANTHROPIC_API_KEY` into LangSmith's own **Secrets & API keys** panel (Playground → evaluator → Save) — a completely separate credential store from the local `.env` file the SDK path (`langsmith.evaluate()`) reads from. The SDK never needed this; it just uses whatever's in the local environment.

**Why it's friction:** Two credential stores for the same provider key, scoped to two different execution paths (server-side UI evaluators vs. local SDK runs), isn't obvious going in. It's a reasonable architecture (UI evaluators run server-side, so they need server-side secrets) but it's not explained at the point where you hit it — you just get steered into a "Secrets & API keys" popup with no context on why this is a second place to manage the same key.

**Suggested fix:** A one-line inline note next to the API Key Name field the first time a user configures a UI evaluator: *"Server-side evaluators need your key stored in LangSmith directly — this is separate from your local environment variables used by the SDK."*
