"""One-off smoke test: confirm Anthropic + LangSmith credentials work end to end."""
import os

from dotenv import load_dotenv

load_dotenv()

required = ["ANTHROPIC_API_KEY", "LANGSMITH_API_KEY"]
missing = [k for k in required if not os.getenv(k)]
if missing:
    raise SystemExit(f"Missing env vars in .env: {missing}")

from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(model="claude-haiku-4-5-20251001")
response = llm.invoke("Reply with exactly one word: hello")
print("Model replied:", response.content)
print("LANGSMITH_PROJECT:", os.getenv("LANGSMITH_PROJECT"))
print("LANGSMITH_TRACING:", os.getenv("LANGSMITH_TRACING"))
