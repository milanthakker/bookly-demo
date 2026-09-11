"""Arize AX tracing setup.

Tracing is optional: if the Arize credentials are absent the app still starts
and serves traffic, just without spans. Reading them with os.environ[...] at
import time meant one missing variable took down every route, health checks
included.
"""

import os

from dotenv import load_dotenv

load_dotenv()

PROJECT_NAME = os.getenv("ARIZE_PROJECT_NAME", "bookly-support-agent")
_SPACE_ID = os.getenv("ARIZE_SPACE_ID")
_API_KEY = os.getenv("ARIZE_API_KEY")

# None means tracing is disabled; callers must guard before using it.
tracer_provider = None

if _SPACE_ID and _API_KEY:
    from arize.otel import register
    from openinference.instrumentation.anthropic import AnthropicInstrumentor

    tracer_provider = register(
        space_id=_SPACE_ID,
        api_key=_API_KEY,
        project_name=PROJECT_NAME,
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
