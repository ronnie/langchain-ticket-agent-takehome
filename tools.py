"""Small in-memory 'tools' the specialist nodes call, standing in for a real
billing system / knowledge base so the agent has something concrete to ground
its response in (rather than just the raw ticket text)."""

BILLING_POLICY = (
    "Refund policy: full refunds within 30 days of purchase, no questions asked. "
    "Refunds over $100 or older than 30 days require manager approval — do not "
    "promise these directly, flag for human review instead."
)

KB_ARTICLES = {
    "login": "Login issues: ask the user to clear cookies for the site and try "
              "an incognito window first. If that fails, check our status page "
              "for an ongoing outage before assuming it's account-specific.",
    "password": "Password resets: the reset link expires in 15 minutes. If the "
                "user says the link 'doesn't work', it's almost always expired — "
                "have them request a fresh one rather than debugging the old link.",
    "crash": "Crashes/errors: ask for the exact error message and what they were "
             "doing when it happened. Check our status page for known incidents "
             "before treating it as a one-off bug.",
    "slow": "Performance complaints: ask which specific action feels slow and "
            "roughly how long it takes. Generic 'it's slow' reports usually need "
            "one clarifying question before they're actionable.",
}


def lookup_billing_policy() -> str:
    return BILLING_POLICY


def search_kb(query: str) -> str:
    query_lower = query.lower()
    for keyword, article in KB_ARTICLES.items():
        if keyword in query_lower:
            return article
    return (
        "No specific KB article matched. Ask a clarifying question before "
        "attempting a fix."
    )
