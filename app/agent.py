import json
import anthropic
from typing import Generator
from dotenv import load_dotenv
from app.tools import TOOL_DEFINITIONS, execute_tool
from app import sessions

load_dotenv()

client = anthropic.Anthropic()

MODEL = "claude-sonnet-4-6"
AUTH_ERROR = "Unsuccessful authentication to Claude."

BASE_SYSTEM_PROMPT = """You are a helpful customer service agent for Bookly, a book discovery and recommendation platform.
You help customers with:
- Finding book recommendations based on their interests
- Managing their account and orders
- Resolving issues with purchases or subscriptions
- Answering questions about the platform

When a customer asks about their orders, use get_customer_orders (requires their email) to list all orders, \
or get_order_details (requires an order ID) to look up a specific order.
Do not ask for information you already know from the session context below.
Be friendly, concise, and always try to resolve the customer's issue in as few turns as possible."""


def _build_system_prompt(session_id: str) -> str:
    session = sessions.get_or_create(session_id)
    context_lines = []
    if session.customer_name or session.customer_email:
        context_lines.append(f"Customer name: {session.customer_name or 'unknown'}")
        context_lines.append(f"Customer email: {session.customer_email or 'unknown'}")
    if session.active_order_id:
        context_lines.append(f"Currently discussed order ID: {session.active_order_id}")

    if not context_lines:
        return BASE_SYSTEM_PROMPT

    context_block = "Known session context (do not ask the customer for this again):\n" + "\n".join(context_lines)
    return f"{BASE_SYSTEM_PROMPT}\n\n{context_block}"


def _update_session_from_tool(session_id: str, tool_name: str, result: str):
    try:
        data = json.loads(result)
    except json.JSONDecodeError:
        return

    if tool_name == "get_customer_orders":
        sessions.update(
            session_id,
            customer_name=data.get("customer_name"),
            customer_email=data.get("customer_email"),
        )
    elif tool_name == "get_order_details":
        sessions.update(
            session_id,
            customer_name=data.get("customer_name"),
            customer_email=data.get("customer_email"),
            active_order_id=data.get("order_id"),
        )


def _run_tool_loop(messages: list[dict], session_id: str) -> list[dict]:
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=_build_system_prompt(session_id),
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            return messages

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = execute_tool(block.name, block.input, session_id)
                _update_session_from_tool(session_id, block.name, result)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        messages.append({"role": "user", "content": tool_results})


def chat(messages: list[dict], session_id: str) -> str:
    try:
        messages = _run_tool_loop(list(messages), session_id)
        for block in messages[-1]["content"]:
            if hasattr(block, "text"):
                return block.text
        return ""
    except anthropic.AuthenticationError:
        return AUTH_ERROR


def chat_stream(messages: list[dict], session_id: str) -> Generator[str, None, None]:
    try:
        messages = _run_tool_loop(list(messages), session_id)
        for block in messages[-1]["content"]:
            if hasattr(block, "text"):
                yield block.text
    except anthropic.AuthenticationError:
        yield AUTH_ERROR
