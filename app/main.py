from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from app.tracing import tracer_provider  # noqa: E402 -- must instrument before app.agent imports anthropic
from app.agent import chat, chat_stream
from app.database import ensure_ready
from opentelemetry.context import attach, detach
from opentelemetry.propagate import extract

@asynccontextmanager
async def lifespan(app: FastAPI):
    # The in-memory database is empty on every cold start. ensure_ready() is
    # also called on first DB access, so seeding still happens on hosts that
    # skip ASGI lifespan startup.
    ensure_ready()
    yield
    # Spans are exported as they end (SimpleSpanProcessor), so this is only a
    # safety net for locally buffered state. tracer_provider is None when the
    # Arize credentials are not configured.
    if tracer_provider is not None:
        tracer_provider.force_flush()
        tracer_provider.shutdown()


app = FastAPI(title="Bookly Customer Service Agent", lifespan=lifespan)

# Permissive CORS so the agent can be invoked from a browser on another origin
# or from a remote evaluation harness. Tighten this for anything non-demo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    session_id: str
    stream: bool = False
    # Identity supplied per invocation, so a caller (or an Arize experiment
    # dataset) can carry it as a plain field instead of establishing it
    # conversationally. Optional: omit it and the agent asks for an email.
    auth_token: str | None = None
    # Arize adds this on remote-agent experiment replays. It carries the space
    # and project to route spans to, plus the experiment/run/example/dataset
    # ids that link those spans back to the experiment row.
    arize_metadata: dict | None = None


@app.get("/")
def index():
    return FileResponse(static_dir / "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat_endpoint(req: ChatRequest, request: Request):
    messages = [m.model_dump() for m in req.messages]

    # Join the caller's trace when it propagates W3C headers (Arize does), so
    # the agent's spans hang off the experiment's trace instead of starting a
    # detached one.
    token = attach(extract(dict(request.headers)))
    try:
        if req.stream:
            return StreamingResponse(
                chat_stream(messages, req.session_id, req.auth_token, req.arize_metadata),
                media_type="text/event-stream",
            )

        return {"response": chat(messages, req.session_id, req.auth_token, req.arize_metadata)}
    finally:
        detach(token)
