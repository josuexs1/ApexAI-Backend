from typing import List, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import os

from elevenlabs.client import ElevenLabs

from app.agent import run_agent
from app.ollama_client import ollama_client
from app.config import settings

limiter = Limiter(key_func=get_remote_address)

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")
eleven_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

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

class HistoryMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    prompt: str
    think: bool = False
    search: bool = False
    images: Optional[List[str]] = None
    history: Optional[List[HistoryMessage]] = None

class DecisionCardOut(BaseModel):
    title: str
    description: str
    badge: Optional[str] = None
    badgeColor: Optional[int] = None
    primaryAction: str
    secondaryAction: Optional[str] = None

class ChatResponseOut(BaseModel):
    response: str
    thinking: Optional[str] = None
    sources: Optional[List[dict]] = None
    decisionCards: Optional[List[DecisionCardOut]] = None

class TTSRequest(BaseModel):
    text: str

@app.post("/chat", response_model=ChatResponseOut)
@limiter.limit(settings.RATE_LIMIT_PER_MINUTE)
async def chat_endpoint(request: Request, chat_request: ChatRequest):
    try:
        history = [
            {"role": m.role, "content": m.content}
            for m in (chat_request.history or [])
        ]
        result = await run_agent(
            chat_request.prompt,
            chat_request.think,
            chat_request.search,
            chat_request.images,
            history
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tts")
async def generate_voice(text: str):
    try:
        clean_text = text.replace("*", "").replace("#", "").replace("`", "").strip()
        
        if not clean_text:
            raise HTTPException(status_code=400, detail="El texto está vacío")

        audio = eleven_client.text_to_speech.convert(
            voice_id=VOICE_ID,
            text=clean_text,
            model_id="eleven_multilingual_v2",
        )

        return StreamingResponse(audio, media_type="audio/mpeg")
    except Exception as e:
        print(f"Error en ElevenLabs: {e}")
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
