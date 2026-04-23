import anthropic
from typing import Generator

client = anthropic.Anthropic()

SYSTEM_PROMPT = """You are a helpful customer service agent for Bookly, a book discovery and recommendation platform.
You help customers with:
- Finding book recommendations based on their interests
- Managing their account and orders
- Resolving issues with purchases or subscriptions
- Answering questions about the platform

Be friendly, concise, and always try to resolve the customer's issue in as few turns as possible."""


def chat(messages: list[dict]) -> str:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    return response.content[0].text


def chat_stream(messages: list[dict]) -> Generator[str, None, None]:
    with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield text
