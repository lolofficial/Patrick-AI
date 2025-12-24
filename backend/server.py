from fastapi import FastAPI, APIRouter, HTTPException, Path, Body, Request, Depends from fastapi.responses import StreamingResponse, JSONResponse from starlette.middleware.cors import CORSMiddleware from motor.motor_asyncio import AsyncIOMotorClient from pydantic import BaseModel, Field, EmailStr from typing import List, Optional, Literal, AsyncGenerator from datetime import datetime, timedelta from jose import jwt, JWTError from passlib.hash import bcrypt import os, uuid, asyncio, json, logging, requests

app = FastAPI() api = APIRouter(prefix="/api")

MONGO_URL = os.environ.get("MONGO_URL") DB_NAME = os.environ.get("DB_NAME", "chatdb") client = AsyncIOMotorClient(MONGO_URL) if MONGO_URL else None db = client[DB_NAME] if client else None

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me") ALGORITHM = "HS256" ACCESS_MIN = 60 * 24 * 7

def create_token(uid: str) -> str: exp = datetime.utcnow() + timedelta(minutes=ACCESS_MIN) return jwt.encode({"sub": uid, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)

async def current_user(request: Request): token = None auth = request.headers.get("Authorization") if auth and auth.startswith("Bearer "): token = auth.split(" ", 1)[1] if not token: cookie = request.cookies.get("access_token") if cookie and cookie.startswith("Bearer "): token = cookie.split(" ", 1)[1] if not token: raise HTTPException(status_code=401, detail="Not authenticated") try: payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]) uid = payload.get("sub") except JWTError: raise HTTPException(status_code=401, detail="Invalid token") user = await db.users.find_one({"_id": uid}) if not user: raise HTTPException(status_code=401, detail="User not found") return {"id": user["_id"], "email": user["email"], "createdAt": user["createdAt"]}

Role = Literal["user", "assistant", "system"]

class RegisterInput(BaseModel): email: EmailStr password: str

class LoginInput(BaseModel): email: EmailStr password: str

class UserPublic(BaseModel): id: str email: EmailStr createdAt: datetime

class SessionModel(BaseModel): id: str = Field(default_factory=lambda: str(uuid.uuid4())) ownerId: str title: str = "Nuova chat" model: str = "gpt-4o-mini" createdAt: datetime = Field(default_factory=datetime.utcnow) updatedAt: datetime = Field(default_factory=datetime.utcnow)

class SessionUpdate(BaseModel): title: Optional[str] = None model: Optional[str] = None

class MessageModel(BaseModel): id: str = Field(default_factory=lambda: str(uuid.uuid4())) ownerId: str sessionId: str role: Role content: str createdAt: datetime = Field(default_factory=datetime.utcnow)

class ChatStreamInput(BaseModel): sessionId: str model: str messages: List[dict] temperature: Optional[float] = 0.3

def to_session(doc) -> SessionModel: return SessionModel( id=doc.get("_id") or doc.get("id"), ownerId=doc["ownerId"], title=doc.get("title", "Nuova chat"), model=doc.get("model", "gpt-4o-mini"), createdAt=doc.get("createdAt", datetime.utcnow()), updatedAt=doc.get("updatedAt", datetime.utcnow()), )

def session_doc(s: SessionModel): return {"_id": s.id, "ownerId": s.ownerId, "title": s.title, "model": s.model, "createdAt": s.createdAt, "updatedAt": s.updatedAt}

def to_message(doc) -> MessageModel: return MessageModel( id=doc.get("_id") or doc.get("id"), ownerId=doc["ownerId"], sessionId=doc["sessionId"], role=doc["role"], content=doc.get("content", ""), createdAt=doc.get("createdAt", datetime.utcnow()), )

def message_doc(m: MessageModel): return {"_id": m.id, "ownerId": m.ownerId, "sessionId": m.sessionId, "role": m.role, "content": m.content, "createdAt": m.createdAt}

@api.get("/") async def hello(): return {"message": "Hello World"}

@api.post("/auth/register", response_model=UserPublic) async def register(inp: RegisterInput): existing = await db.users.find_one({"email": inp.email}) if existing: if bcrypt.verify(inp.password, existing.get("passwordHash", "")): token = create_token(existing["_id"]) resp = JSONResponse(UserPublic(id=existing["_id"], email=existing["email"], createdAt=existing["createdAt"]).dict()) resp.set_cookie("access_token", f"Bearer {token}", httponly=True, samesite="lax", secure=False, path="/") return resp raise HTTPException(status_code=409, detail="Email già registrata, password non corretta") uid = str(uuid.uuid4()) doc = {"_id": uid, "email": inp.email, "passwordHash": bcrypt.hash(inp.password), "createdAt": datetime.utcnow()} await db.users.insert_one(doc) token = create_token(uid) resp = JSONResponse(UserPublic(id=uid, email=inp.email, createdAt=doc["createdAt"]).dict()) resp.set_cookie("access_token", f"Bearer {token}", httponly=True, samesite="lax", secure=False, path="/") return resp

@api.post("/auth/login", response_model=UserPublic) async def login(inp: LoginInput): user = await db.users.find_one({"email": inp.email}) if not user or not bcrypt.verify(inp.password, user.get("passwordHash", "")): raise HTTPException(status_code=401, detail="Credenziali non valide") token = create_token(user["_id"]) resp = JSONResponse(UserPublic(id=user["_id"], email=user["email"], createdAt=user["createdAt"]).dict()) resp.set_cookie("access_token", f"Bearer {token}", httponly=True, samesite="lax", secure=False, path="/") return resp

@api.get("/auth/me", response_model=UserPublic) async def me(u=Depends(current_user)): return UserPublic(id=u["id"], email=u["email"], createdAt=u["createdAt"])

@api.post("/auth/logout") async def logout(): resp = JSONResponse({"ok": True}) resp.delete_cookie("access_token", path="/") return resp

@api.get("/sessions", response_model=List[SessionModel]) async def sessions_list(u=Depends(current_user)): docs = await db.sessions.find({"ownerId": u["id"]}).sort("updatedAt", -1).to_list(200) return [to_session(d) for d in docs]

@api.post("/sessions", response_model=SessionModel, status_code=201) async def sessions_create(u=Depends(current_user)): s = SessionModel(ownerId=u["id"]) await db.sessions.insert_one(session_doc(s)) return s

@api.put("/sessions/{sid}", response_model=SessionModel) async def sessions_update(sid: str, body: SessionUpdate, u=Depends(current_user)): doc = await db.sessions.find_one({"_id": sid, "ownerId": u["id"]}) if not doc: raise HTTPException(status_code=404, detail="Session not found") s = to_session(doc) if body.title is not None: s.title = body.title if body.model is not None: s.model = body.model s.updatedAt = datetime.utcnow() await db.sessions.update_one({"_id": sid, "ownerId": u["id"]}, {"$set": session_doc(s)}) return s

@api.delete("/sessions/{sid}", status_code=204) async def sessions_delete(sid: str, u=Depends(current_user)): await db.messages.delete_many({"sessionId": sid, "ownerId": u["id"]}) await db.sessions.delete_one({"_id": sid, "ownerId": u["id"]}) return

@api.get("/sessions/{sid}/messages", response_model=List[MessageModel]) async def messages_get(sid: str, u=Depends(current_user)): sess = await db.sessions.find_one({"_id": sid, "ownerId": u["id"]}) if not sess: raise HTTPException(status_code=404, detail="Session not found") docs = await db.messages.find({"sessionId": sid, "ownerId": u["id"]}).sort("createdAt", 1).to_list(1000) return [to_message(d) for d in docs]

async def mock_delta(prompt: str) -> AsyncGenerator[str, None]: text = f"Certo! Risposta mock per: '{prompt[:60]}'. Questa è una demo streaming." for w in text.split(" "): await asyncio.sleep(0.03) yield w + " "

def openai_stream_generator(messages: List[dict], model: str, temperature: float): api_key = os.environ.get("OPENAI_API_KEY") if not api_key: raise RuntimeError("OPENAI_API_KEY not configured") model_map = {"gpt-4o": "gpt-4o", "gpt-4o-mini": "gpt-4o-mini"} mdl = model_map.get(model, "gpt-4o-mini") resp = requests.post( "https://api.openai.com/v1/chat/completions", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json={"model": mdl, "messages": messages, "temperature": temperature, "stream": True}, stream=True, timeout=600, ) if resp.status_code != 200: raise RuntimeError(f"OpenAI error {resp.status_code}: {resp.text[:200]}") for raw in resp.iter_lines(decode_unicode=True): if not raw: continue if raw.startswith("data:"): data = raw[5:].strip() if data == "[DONE]": break try: j = json.loads(data) delta = j["choices"][0]["delta"].get("content") if delta: yield delta except Exception: continue

@api.post("/chat/stream") async def chat_stream(body: ChatStreamInput, request: Request, u=Depends(current_user)): sess = await db.sessions.find_one({"_id": body.sessionId, "ownerId": u["id"]}) if not sess: raise HTTPException(status_code=404, detail="Session not found") last_user = "" for m in reversed(body.messages or []): if m.get("role") == "user": last_user = m.get("content", "") break user_msg = MessageModel(ownerId=u["id"], sessionId=body.sessionId, role="user", content=last_user) await db.messages.insert_one(message_doc(user_msg)) async def gen(): full = "" try: try: for delta in openai_stream_generator(body.messages, body.model, body.temperature or 0.3): full += delta if await request.is_disconnected(): break yield f"data: {{"type":"chunk","delta": {json.dumps(delta)} }}\n\n" except Exception as e: logging.warning(f"OpenAI fallback: {e}") async for delta in mock_delta(last_user): full += delta if await request.is_disconnected(): break yield f"data: {{"type":"chunk","delta": {json.dumps(delta)} }}\n\n" assistant = MessageModel(ownerId=u["id"], sessionId=body.sessionId, role="assistant", content=full) await db.messages.insert_one(message_doc(assistant)) yield "data: {"type":"end"}\n\n" except Exception as e: yield f"data: {{"type":"error","error": {json.dumps(str(e))} }}\n\n" return StreamingResponse(gen(), media_type="text/event-stream")

app.include_router(api)

cors_env = os.environ.get("CORS_ORIGINS", "") origins = [o.strip() for o in cors_env.split(",") if o.strip()] if origins: app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=[""], allow_headers=[""]) else: app.add_middleware(CORSMiddleware, allow_origins=[""], allow_credentials=False, allow_methods=[""], allow_headers=["*"])

@app.on_event("shutdown") async def shutdown_event(): if client: client.close()




