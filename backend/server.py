from fastapi import FastAPI, APIRouter, HTTPException, Path, Body, Request
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path as Pathlib
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, AsyncGenerator
import uuid
import json
from datetime import datetime
import asyncio

ROOT_DIR = Pathlib(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app
app = FastAPI()

# Router with /api prefix
api_router = APIRouter(prefix="/api")

# ----------------- Models -----------------
class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class StatusCheckCreate(BaseModel):
    client_name: str

Role = Literal["user", "assistant", "system"]

class SessionModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "Nuova chat"
    model: str = "gpt-4o-mini"
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

class SessionCreate(BaseModel):
    title: Optional[str] = None
    model: Optional[str] = None

class SessionUpdate(BaseModel):
    title: Optional[str] = None
    model: Optional[str] = None

class MessageModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sessionId: str
    role: Role
    content: str
    createdAt: datetime = Field(default_factory=datetime.utcnow)

class ChatStreamInput(BaseModel):
    sessionId: str
    model: str
    messages: List[MessageModel] | List[dict]
    temperature: Optional[float] = 0.3

# ----------------- Helpers -----------------

def _doc_to_session(doc) -> SessionModel:
    return SessionModel(
        id=doc.get("_id") or doc.get("id"),
        title=doc.get("title", "Nuova chat"),
        model=doc.get("model", "gpt-4o-mini"),
        createdAt=doc.get("createdAt", datetime.utcnow()),
        updatedAt=doc.get("updatedAt", datetime.utcnow()),
    )


def _session_to_doc(s: SessionModel):
    return {
        "_id": s.id,
        "title": s.title,
        "model": s.model,
        "createdAt": s.createdAt,
        "updatedAt": s.updatedAt,
    }


def _doc_to_message(doc) -> MessageModel:
    return MessageModel(
        id=doc.get("_id") or doc.get("id"),
        sessionId=doc["sessionId"],
        role=doc["role"],
        content=doc.get("content", ""),
        createdAt=doc.get("createdAt", datetime.utcnow()),
    )


def _message_to_doc(m: MessageModel):
    return {
        "_id": m.id,
        "sessionId": m.sessionId,
        "role": m.role,
        "content": m.content,
        "createdAt": m.createdAt,
    }

# ----------------- Routes -----------------

@api_router.get("/")
async def root():
    return {"message": "Hello World"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_obj = StatusCheck(**input.dict())
    await db.status_checks.insert_one(status_obj.dict())
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find().to_list(1000)
    return [StatusCheck(**sc) for sc in status_checks]

# Sessions CRUD
@api_router.get("/sessions", response_model=List[SessionModel])
async def list_sessions():
    docs = await db.sessions.find().sort("updatedAt", -1).to_list(100)
    return [_doc_to_session(d) for d in docs]

@api_router.post("/sessions", response_model=SessionModel, status_code=201)
async def create_session(payload: SessionCreate = Body(default_factory=SessionCreate)):
    s = SessionModel(
        title=payload.title or "Nuova chat",
        model=payload.model or "gpt-4o-mini",
    )
    await db.sessions.insert_one(_session_to_doc(s))
    return s

@api_router.put("/sessions/{session_id}", response_model=SessionModel)
async def update_session(session_id: str = Path(...), payload: SessionUpdate = Body(default_factory=SessionUpdate)):
    doc = await db.sessions.find_one({"_id": session_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Session not found")
    s = _doc_to_session(doc)
    if payload.title is not None:
        s.title = payload.title
    if payload.model is not None:
        s.model = payload.model
    s.updatedAt = datetime.utcnow()
    await db.sessions.update_one({"_id": s.id}, {"$set": _session_to_doc(s)})
    return s

@api_router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str = Path(...)):
    await db.messages.delete_many({"sessionId": session_id})
    await db.sessions.delete_one({"_id": session_id})
    return

# Messages
@api_router.get("/sessions/{session_id}/messages", response_model=List[MessageModel])
async def get_messages(session_id: str = Path(...)):
    docs = await db.messages.find({"sessionId": session_id}).sort("createdAt", 1).to_list(1000)
    return [_doc_to_message(d) for d in docs]

# --------- SSE Chat (Mock server-side for now) ---------
async def mock_llm_stream(prompt: str) -> AsyncGenerator[str, None]:
    canned = [
        "Certo! Ti aiuto volentieri. Ecco una spiegazione semplice e diretta.",
        "Ottima domanda. Possiamo affrontarla passo dopo passo.",
        "Ecco un esempio pratico che puoi copiare e provare subito.",
        "Riassumendo in pochi punti: 1) comprendi il problema, 2) applica la soluzione, 3) verifica i risultati.",
        "Posso anche generare una versione più concisa o più dettagliata se preferisci.",
    ]
    import random
    base = random.choice(canned)
    topic = (prompt or "la tua richiesta")[:60]
    full = f"{base}\n\nRiferimento al tema: \"{topic}\".\n\nNota: questa è una risposta mock dal server."
    words = full.split(" ")
    chunk = ""
    for i, w in enumerate(words):
        chunk = ("" if i == 0 else chunk + " ") + w
        await asyncio.sleep(0.05)
        yield chunk

@api_router.post("/chat/stream")
async def chat_stream(input: ChatStreamInput, request: Request):
    # Estrarre ultimo messaggio utente
    user_msgs = [m for m in input.messages if (m.get("role") if isinstance(m, dict) else m.role) == "user"]
    last_user = user_msgs[-1] if user_msgs else None
    prompt = last_user.get("content") if isinstance(last_user, dict) else (last_user.content if last_user else "")

    # Verifica sessione esistente
    sess = await db.sessions.find_one({"_id": input.sessionId})
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    # Salva il messaggio utente
    user_msg = MessageModel(sessionId=input.sessionId, role="user", content=prompt or "")
    await db.messages.insert_one(_message_to_doc(user_msg))

    async def event_gen():
        try:
            # Qui in futuro: integrazione provider LLM reale (OpenAI/Anthropic/Gemini)
            async for partial in mock_llm_stream(prompt or ""):
                if await request.is_disconnected():
                    break
                yield f"data: {{\"type\": \"chunk\", \"delta\": {json.dumps(partial)} }}\n\n"
            # Alla fine, salva il messaggio assistant completo
            assistant_msg = MessageModel(sessionId=input.sessionId, role="assistant", content=partial)
            await db.messages.insert_one(_message_to_doc(assistant_msg))
            yield f"data: {{\"type\": \"end\", \"messageId\": \"{assistant_msg.id}\"}}\n\n"
        except Exception as e:
            logging.exception("stream error")
            yield f"data: {{\"type\": \"error\", \"error\": {str(e)!r} }}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")

# Include router
app.include_router(api_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()