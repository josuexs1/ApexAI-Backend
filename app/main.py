from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.agent import run_agent
from app.ollama_client import ollama_client
from app.config import settings

limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await ollama_client.close()

app = FastAPI(title="Apex AI - Ollama Cloud Agent API", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    prompt: str
    think: bool = False
    search: bool = False

@app.post("/chat")
@limiter.limit(settings.RATE_LIMIT_PER_MINUTE)
async def chat_endpoint(request: Request, chat_request: ChatRequest):
    try:
        result = await run_agent(chat_request.prompt, chat_request.think, chat_request.search)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "ok", "creator": "Josuexs (Venezuela)"}

@app.get("/version")
async def get_version():
    return {
        "version": "1.0.0",
        "changelog": "Mejoras en el rendimiento y corrección de errores."
    }
