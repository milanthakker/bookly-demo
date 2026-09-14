import json
import anthropic
from typing import Generator, Optional
from dotenv import load_dotenv
from opentelemetry.trace import get_tracer, Status, StatusCode
from opentelemetry import baggage
from arize.otel import set_routing_context
from openinference.instrumentation import using_session
from openinference.semconv.trace import SpanAttributes, OpenInferenceSpanKindValues
from app.tools import TOOL_DEFINITIONS, execute_tool, resolve_auth_token
from app import sessions
from app.tracing import DEFAULT_SPACE_ID, PROJECT_NAME

load_dotenv()

client = anthropic.Anthropic()
tracer = get_tracer(__name__)

MODEL = "claude-sonnet-4-6"
AUTH_ERROR = "Unsuccessful authentication to Claude."
INVALID_TOKEN = "Invalid auth token: no matching Bookly customer."

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


def _last_user_text(messages: list[dict]) -> str:
    for message in reversed(messages):
        if message["role"] == "user" and isinstance(message["content"], str):
            return message["content"]
    return ""


def _final_assistant_text(messages: list[dict]) -> str:
    for block in messages[-1]["content"]:
        if hasattr(block, "text"):
            return block.text
    return ""


def _apply_auth_token(session_id: str, auth_token: Optional[str]) -> bool:
    """Seed session identity from an invocation auth token.

    Returns False if the token was supplied but did not resolve, so the caller
    can fail fast without spending a model call.
    """
    if not auth_token:
        return True

    identity = resolve_auth_token(auth_token)
    if identity is None:
        return False

    sessions.update(session_id, **identity)
    return True



# Identifiers Arize sends under `arize_metadata`, stamped onto the chain span as
# bare keys (no prefix) so a run's spans link back to its experiment row.
_EXPERIMENT_KEYS = ("experiment_id", "run_id", "example_id", "dataset_id")


def _metadata_with_baggage(arize_metadata: Optional[dict]) -> dict:
    """Merge the request's `arize_metadata` with any values sent via baggage.

    Arize puts the same identifiers in both places. The body is preferred; the
    baggage fallback keeps experiment linkage working if the body key is absent,
    which would otherwise fail silently by routing spans to the default project.
    Baggage uses bare keys, with no `arize.` prefix.
    """
    merged = {}
    for key in _EXPERIMENT_KEYS + ("space_id", "project_name"):
        value = baggage.get_baggage(key)
        if value:
            merged[key] = value
    merged.update(arize_metadata or {})
    return merged


def _routing_target(arize_metadata: Optional[dict]) -> tuple[Optional[str], Optional[str]]:
    """Resolve which Arize space and project a request's spans belong to.

    An experiment names its own target; everything else falls back to the
    configured defaults. arize-otel drops spans unless BOTH values are set, so
    never return a half-populated pair.
    """
    md = arize_metadata or {}
    space_id = md.get("space_id") or DEFAULT_SPACE_ID
    project_name = md.get("project_name") or PROJECT_NAME
    if not space_id or not project_name:
        return None, None
    return space_id, project_name


def _run_tool_loop(
    messages: list[dict], session_id: str, arize_metadata: Optional[dict] = None
) -> list[dict]:
    arize_metadata = _metadata_with_baggage(arize_metadata)
    space_id, project_name = _routing_target(arize_metadata)
    with using_session(session_id=session_id), set_routing_context(
        space_id=space_id or "", project_name=project_name or ""
    ):
        with tracer.start_as_current_span("run_tool_loop") as chain_span:
            chain_span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.CHAIN.value)
            chain_span.set_attribute(SpanAttributes.INPUT_VALUE, _last_user_text(messages))
            for key in _EXPERIMENT_KEYS:
                value = (arize_metadata or {}).get(key)
                if value:
                    chain_span.set_attribute(key, str(value))
            try:
                messages = _run_tool_loop_inner(messages, session_id)
                chain_span.set_attribute(SpanAttributes.OUTPUT_VALUE, _final_assistant_text(messages))
            except Exception as e:
                chain_span.set_status(Status(StatusCode.ERROR))
                chain_span.record_exception(e)
                raise
            else:
                chain_span.set_status(Status(StatusCode.OK))
            return messages


def _run_tool_loop_inner(messages: list[dict], session_id: str) -> list[dict]:
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
                with tracer.start_as_current_span(block.name) as tool_span:
                    tool_span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.TOOL.value)
                    tool_span.set_attribute(SpanAttributes.TOOL_NAME, block.name)
                    tool_span.set_attribute(SpanAttributes.TOOL_PARAMETERS, json.dumps(block.input))
                    tool_span.set_attribute(SpanAttributes.INPUT_VALUE, json.dumps(block.input))
                    try:
                        result = execute_tool(block.name, block.input, session_id)
                    except Exception as e:
                        tool_span.set_status(Status(StatusCode.ERROR))
                        tool_span.record_exception(e)
                        raise
                    tool_span.set_attribute(SpanAttributes.OUTPUT_VALUE, result)
                    tool_span.set_status(Status(StatusCode.OK))
                _update_session_from_tool(session_id, block.name, result)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        messages.append({"role": "user", "content": tool_results})


def chat(
    messages: list[dict],
    session_id: str,
    auth_token: Optional[str] = None,
    arize_metadata: Optional[dict] = None,
) -> str:
    if not _apply_auth_token(session_id, auth_token):
        return INVALID_TOKEN
    try:
        messages = _run_tool_loop(list(messages), session_id, arize_metadata)
        return _final_assistant_text(messages)
    except anthropic.AuthenticationError:
        return AUTH_ERROR


def chat_stream(
    messages: list[dict],
    session_id: str,
    auth_token: Optional[str] = None,
    arize_metadata: Optional[dict] = None,
) -> Generator[str, None, None]:
    if not _apply_auth_token(session_id, auth_token):
        yield INVALID_TOKEN
        return
    try:
        messages = _run_tool_loop(list(messages), session_id, arize_metadata)
        yield _final_assistant_text(messages)
    except anthropic.AuthenticationError:
        yield AUTH_ERROR
