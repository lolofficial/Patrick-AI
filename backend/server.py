from fastapi import FastAPI, APIRouter, HTTPException, Path, Body, Request, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path as Pathlib
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Literal, AsyncGenerator
import uuid
from datetime import datetime, timedelta
import asyncio
import json
import requests
from jose import jwt, JWTError
from passlib.hash import bcrypt
from fastapi.encoders import jsonable_encoder

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

# ----------------- Auth Config -----------------
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 giorni

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
    ownerId: str
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
    ownerId: str
    sessionId: str
    role: Role
    content: str
    createdAt: datetime = Field(default_factory=datetime.utcnow)

class ChatStreamInput(BaseModel):
    sessionId: str
    model: str
    messages: List[MessageModel] | List[dict]
    temperature: Optional[float] = 0.3

class UserPublic(BaseModel):
    id: str
    email: EmailStr
    createdAt: datetime

class RegisterInput(BaseModel):
    email: EmailStr
    password: str

class LoginInput(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    user: UserPublic
    token: str

# ----------------- Helpers -----------------

def _doc_to_session(doc) -> SessionModel:
    return SessionModel(
        id=doc.get("_id") or doc.get("id"),
        ownerId=doc.get("ownerId"),
        title=doc.get("title", "Nuova chat"),
        model=doc.get("model", "gpt-4o-mini"),
        createdAt=doc.get("createdAt", datetime.utcnow()),
        updatedAt=doc.get("updatedAt", datetime.utcnow()),
    )


def _session_to_doc(s: SessionModel):
    return {
        "_id": s.id,
        "ownerId": s.ownerId,
        "title": s.title,
        "model": s.model,
        "createdAt": s.createdAt,
        "updatedAt": s.updatedAt,
    }


def _doc_to_message(doc) -> MessageModel:
    return MessageModel(
        id=doc.get("_id") or doc.get("id"),
        ownerId=doc.get("ownerId"),
        sessionId=doc["sessionId"],
        role=doc["role"],
        content=doc.get("content", ""),
        createdAt=doc.get("createdAt", datetime.utcnow()),
    )


def _message_to_doc(m: MessageModel):
    return {
        "_id": m.id,
        "ownerId": m.ownerId,
        "sessionId": m.sessionId,
        "role": m.role,
        "content": m.content,
        "createdAt": m.createdAt,
    }

async def _find_user_by_email(email: str):
    return await db.users.find_one({"email": email})

# ----------------- Auth utils -----------------

def create_access_token(sub: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": sub, "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(request: Request) -> UserPublic:
    token = None
    # from cookie
    cookie = request.cookies.get("access_token")
    if cookie and cookie.startswith("Bearer "):
        token = cookie.split(" ", 1)[1]
    # from header
    if not token:
        auth = request.headers.get("Authorization")
        if auth and auth.startswith("Bearer "):
            token = auth.split(" ", 1)[1]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uid = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_doc = await db.users.find_one({"_id": uid})
    if not user_doc:
        raise HTTPException(status_code=401, detail="User not found")
    return UserPublic(id=user_doc["_id"], email=user_doc["email"], createdAt=user_doc["createdAt"])

# ----------------- Routes -----------------

@api_router.get("/")
async def root():
    return {"message": "Hello World"}

# Auth endpoints
@api_router.post("/auth/register", response_model=AuthResponse)
async def register(input: RegisterInput):
    existing = await _find_user_by_email(input.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email già registrata")
    uid = str(uuid.uuid4())
    user_doc = {
        "_id": uid,
        "email": input.email,
        "passwordHash": bcrypt.hash(input.password),
        "createdAt": datetime.utcnow(),
    }
    await db.users.insert_one(user_doc)
    token = create_access_token(uid)
    resp_data = AuthResponse(user=UserPublic(id=uid, email=input.email, createdAt=user_doc["createdAt"]), token=token)
    resp = JSONResponse(jsonable_encoder(resp_data))
    # set also cookie for same-site scenarios
    resp.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return resp

@api_router.post("/auth/login", response_model=AuthResponse)
async def login(input: LoginInput):
    user = await _find_user_by_email(input.email)
    if not user or not bcrypt.verify(input.password, user.get("passwordHash", "")):
        raise HTTPException(status_code=401, detail="Credenziali non valide")
    token = create_access_token(user["_id"])
    resp_data = AuthResponse(user=UserPublic(id=user["_id"], email=user["email"], createdAt=user["createdAt"]), token=token)
    resp = JSONResponse(jsonable_encoder(resp_data))
    resp.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return resp

@api_router.post("/auth/logout")
async def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("access_token", path="/")
    return resp

@api_router.get("/auth/me", response_model=UserPublic)
async def me(user: UserPublic = Depends(get_current_user)):
    return user

# Sessions CRUD (auth required)
@api_router.get("/sessions", response_model=List[SessionModel])
async def list_sessions(user: UserPublic = Depends(get_current_user)):
    docs = await db.sessions.find({"ownerId": user.id}).sort("updatedAt", -1).to_list(100)
    return [_doc_to_session(d) for d in docs]

@api_router.post("/sessions", response_model=SessionModel, status_code=201)
async def create_session(payload: SessionCreate = Body(default_factory=SessionCreate), user: UserPublic = Depends(get_current_user)):
    s = SessionModel(
        ownerId=user.id,
        title=payload.title or "Nuova chat",
        model=payload.model or "gpt-4o-mini",
    )
    await db.sessions.insert_one(_session_to_doc(s))
    return s

@api_router.put("/sessions/{session_id}", response_model=SessionModel)
async def update_session(session_id: str = Path(...), payload: SessionUpdate = Body(default_factory=SessionUpdate), user: UserPublic = Depends(get_current_user)):
    doc = await db.sessions.find_one({"_id": session_id, "ownerId": user.id})
    if not doc:
        raise HTTPException(status_code=404, detail="Session not found")
    s = _doc_to_session(doc)
    if payload.title is not None:
        s.title = payload.title
    if payload.model is not None:
        s.model = payload.model
    s.updatedAt = datetime.utcnow()
    await db.sessions.update_one({"_id": s.id, "ownerId": user.id}, {"$set": _session_to_doc(s)})
    return s

@api_router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str = Path(...), user: UserPublic = Depends(get_current_user)):
    await db.messages.delete_many({"sessionId": session_id, "ownerId": user.id})
    await db.sessions.delete_one({"_id": session_id, "ownerId": user.id})
    return

# Messages
@api_router.get("/sessions/{session_id}/messages", response_model=List[MessageModel])
async def get_messages(session_id: str = Path(...), user: UserPublic = Depends(get_current_user)):
    # ensure session belongs to user
    sess = await db.sessions.find_one({"_id": session_id, "ownerId": user.id})
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    docs = await db.messages.find({"sessionId": session_id, "ownerId": user.id}).sort("createdAt", 1).to_list(1000)
    return [_doc_to_message(d) for d in docs]

# --------- LLM integration helpers ---------
async def mock_llm_stream_delta(prompt: str) -> AsyncGenerator[str, None]:
    """Yield piccoli delta (parole) come streaming mock."""
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
    for w in full.split(" "):
        yield (w + " ")
        await asyncio.sleep(0.03)

async def openai_chat_stream_delta(messages: List[dict], model: str, temperature: float = 0.3) -> AsyncGenerator[str, None]:
    """Chiama OpenAI con stream=true e produce delta di testo (token/word)."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not configured")

    model_map = {"gpt-4o": "gpt-4o", "gpt-4o-mini": "gpt-4o-mini"}
    model = model_map.get(model, "gpt-4o-mini")

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    with requests.post(url, headers=headers, json=payload, stream=True, timeout=600) as resp:
        if resp.status_code != 200:
            text = resp.text[:500]
            logging.error("OpenAI stream error %s: %s", resp.status_code, text)
            raise RuntimeError(f"OpenAI API error {resp.status_code}")
        for raw_line in resp.iter_lines(decode_unicode=True):
            if raw_line is None:
                continue
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("data:"):
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                try:
                    j = json.loads(data)
                except Exception:
                    continue
                try:
                    delta = j["choices"][0]["delta"].get("content")
                except Exception:
                    delta = None
                if delta:
                    yield delta

# --------- SSE Chat (token-by-token) ---------
@api_router.post("/chat/stream")
async def chat_stream(input: ChatStreamInput, request: Request, user: UserPublic = Depends(get_current_user)):
    # Costruisci history
    in_msgs = []
    for m in input.messages:
        if isinstance(m, dict):
            in_msgs.append({"role": m.get("role"), "content": m.get("content", "")})
        else:
            in_msgs.append({"role": m.role, "content": m.content})

    # Verifica sessione esistente e ownership
    sess = await db.sessions.find_one({"_id": input.sessionId, "ownerId": user.id})
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    # Salva il messaggio utente (ultimo user)
    last_user_content = next((m["content"] for m in reversed(in_msgs) if m["role"] == "user"), "")
    user_msg = MessageModel(ownerId=user.id, sessionId=input.sessionId, role="user", content=last_user_content)
    await db.messages.insert_one(_message_to_doc(user_msg))

    async def event_gen():
        full_answer = ""
        try:
            api_key = os.environ.get("OPENAI_API_KEY")
            delta_stream: AsyncGenerator[str, None]
            if api_key:
                delta_stream = openai_chat_stream_delta(in_msgs, input.model, input.temperature or 0.3)
            else:
                delta_stream = mock_llm_stream_delta(last_user_content)

            async for piece in delta_stream:
                if await request.is_disconnected():
                    break
                full_answer += piece
                yield f"data: {{\"type\": \"chunk\", \"delta\": {json.dumps(piece)} }}\n\n"

            assistant_msg = MessageModel(ownerId=user.id, sessionId=input.sessionId, role="assistant", content=full_answer)
            await db.messages.insert_one(_message_to_doc(assistant_msg))
            yield f"data: {{\"type\": \"end\", \"messageId\": \"{assistant_msg.id}\"}}\n\n"
        except Exception as e:
            logging.exception("stream error")
            yield f"data: {{\"type\": \"error\", \"error\": {json.dumps(str(e))} }}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")

# Include router
app.include_router(api_router)

# CORS: se CORS_ORIGINS è "*", per richieste con credenziali usiamo localhost:3000 di default
cors_env = os.environ.get("CORS_ORIGINS", "*")
origins = [o.strip() for o in cors_env.split(",") if o.strip()] if cors_env else ["http://localhost:3000"]
if origins == ["*"]:
    origins = ["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()