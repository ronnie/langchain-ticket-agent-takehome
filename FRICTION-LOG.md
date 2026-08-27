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
