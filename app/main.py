from fastapi import FastAPI
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv
from app.agent import chat, chat_stream
from app.database import init_db

load_dotenv()

app = FastAPI(title="Bookly Customer Service Agent")


@app.on_event("startup")
def startup():
    init_db()

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    session_id: str
    stream: bool = False


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
            chat_stream(messages, req.session_id),
            media_type="text/event-stream",
        )

    return {"response": chat(messages, req.session_id)}
