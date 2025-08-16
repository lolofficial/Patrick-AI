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

class ChangePasswordInput(BaseModel):
    currentPassword: str
    newPassword: str

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
    cookie = request.cookies.get("access_token")
    if cookie and cookie.startswith("Bearer "):
        token = cookie.split(" ", 1)[1]
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

@api_router.post("/auth/change-password")
async def change_password(input: ChangePasswordInput, user: UserPublic = Depends(get_current_user)):
    if len(input.newPassword) < 6:
        raise HTTPException(status_code=400, detail="La nuova password deve avere almeno 6 caratteri")
    doc = await db.users.find_one({"_id": user.id})
    if not doc or not bcrypt.verify(input.currentPassword, doc.get("passwordHash", "")):
        raise HTTPException(status_code=401, detail="Password attuale non corretta")
    new_hash = bcrypt.hash(input.newPassword)
    await db.users.update_one({"_id": user.id}, {"$set": {"passwordHash": new_hash}})
    return {"ok": True}

# ... rest of file unchanged ...