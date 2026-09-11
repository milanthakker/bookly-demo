"""Invoke a hosted Bookly agent over JSON.

The agent is a plain HTTP endpoint, so an evaluation harness only needs a task
function that maps one dataset row to one request. Identity travels in the
`auth_token` field, so it can live in the dataset alongside the query.

    BOOKLY_URL=https://<your-deployment>.vercel.app python examples/invoke_agent.py
"""

import os
import json
import urllib.request

BOOKLY_URL = os.getenv("BOOKLY_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = float(os.getenv("BOOKLY_TIMEOUT", "120"))


def ask(query: str, auth_token: str | None = None, session_id: str | None = None) -> str:
    """Send one query to the agent and return its reply."""
    payload = {
        "session_id": session_id or f"run-{abs(hash((query, auth_token))) % 10**8}",
        "messages": [{"role": "user", "content": query}],
    }
    if auth_token:
        payload["auth_token"] = auth_token

    request = urllib.request.Request(
        f"{BOOKLY_URL}/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.load(response)["response"]


def task(row: dict) -> str:
    """Arize experiment task: one dataset row in, agent output out.

    Expects columns `query` and (optionally) `auth_token`. Pass this straight to
    your experiment runner as the task, then score the returned string with
    whichever evaluators you want.
    """
    return ask(row["query"], row.get("auth_token"))


# A dataset shaped the way `task` expects.
EXAMPLE_ROWS = [
    {"query": "What orders do I have?", "auth_token": "alice@example.com"},
    {"query": "What is the payment breakdown for order 5?", "auth_token": "clara@example.com"},
    {"query": "Refund order 7, I changed my mind.", "auth_token": "david@example.com"},
    {"query": "Refund order 8 please.", "auth_token": "david@example.com"},
    {"query": "Show me the details of order 5.", "auth_token": "eva@example.com"},
    {"query": "What is your return policy?", "auth_token": None},
]


if __name__ == "__main__":
    print(f"agent: {BOOKLY_URL}\n")
    for row in EXAMPLE_ROWS:
        print(f"Q ({row['auth_token'] or 'anonymous'}): {row['query']}")
        print(f"A: {task(row)}\n")
