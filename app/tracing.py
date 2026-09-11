import os

from dotenv import load_dotenv
from arize.otel import register
from openinference.instrumentation.anthropic import AnthropicInstrumentor

load_dotenv()

PROJECT_NAME = os.getenv("ARIZE_PROJECT_NAME", "bookly-support-agent")

tracer_provider = register(
    space_id=os.environ["ARIZE_SPACE_ID"],
    api_key=os.environ["ARIZE_API_KEY"],
    project_name=PROJECT_NAME,
    # SimpleSpanProcessor exports each span as it ends, instead of batching in a
    # background thread. Serverless hosts freeze the process right after the
    # response, which loses whatever a BatchSpanProcessor still had queued.
    batch=False,
)

AnthropicInstrumentor().instrument(tracer_provider=tracer_provider)
