from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from app.agent import chat, chat_stream

load_dotenv()

app = FastAPI(title="Bookly Customer Service Agent")


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    stream: bool = False


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat_endpoint(req: ChatRequest):
    messages = [m.model_dump() for m in req.messages]

    if req.stream:
        return StreamingResponse(
            chat_stream(messages),
            media_type="text/event-stream",
        )

    return {"response": chat(messages)}
