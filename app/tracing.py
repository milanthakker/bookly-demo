"""Arize AX tracing setup.

Tracing is optional: if the Arize credentials are absent the app still starts
and serves traffic, just without spans.

Registration is routing-aware (`register_with_routing`) so that a remote-agent
experiment can direct its spans to the space and project named in the request's
`arize_metadata`. The tradeoff is that arize-otel DROPS any span produced
outside a `set_routing_context(...)` block, so every traced path must open one --
see `DEFAULT_SPACE_ID` / `PROJECT_NAME`, used for ordinary (non-experiment)
traffic.
"""

import os

from dotenv import load_dotenv

load_dotenv()

PROJECT_NAME = os.getenv("ARIZE_PROJECT_NAME", "bookly-support-agent")
DEFAULT_SPACE_ID = os.getenv("ARIZE_SPACE_ID")
_API_KEY = os.getenv("ARIZE_API_KEY")

# None means tracing is disabled; callers must guard before using it.
tracer_provider = None

if DEFAULT_SPACE_ID and _API_KEY:
    from arize.otel import register_with_routing
    from openinference.instrumentation.anthropic import AnthropicInstrumentor

    tracer_provider = register_with_routing(
        api_key=_API_KEY,
        # SimpleSpanProcessor exports each span as it ends, instead of batching in a
        # background thread. Serverless hosts freeze the process right after the
        # response, which loses whatever a BatchSpanProcessor still had queued.
        batch=False,
    )
    AnthropicInstrumentor().instrument(tracer_provider=tracer_provider)
else:
    print(
        "Arize tracing disabled: set ARIZE_SPACE_ID and ARIZE_API_KEY to enable it."
    )
