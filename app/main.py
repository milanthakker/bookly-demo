from contextlib import asynccontextmanager

from fastapi import FastAPI
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # The in-memory database is empty on every cold start. ensure_ready() is
    # also called on first DB access, so seeding still happens on hosts that
    # skip ASGI lifespan startup.
    ensure_ready()
    yield
    # Spans are exported as they end (SimpleSpanProcessor), so this is only a
    # safety net for locally buffered state.
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


@app.get("/")
def index():
    return FileResponse(static_dir / "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat_endpoint(req: ChatRequest):
    messages = [m.model_dump() for m in req.messages]

    if req.stream:
        return StreamingResponse(
            chat_stream(messages, req.session_id, req.auth_token),
            media_type="text/event-stream",
        )

    return {"response": chat(messages, req.session_id, req.auth_token)}
