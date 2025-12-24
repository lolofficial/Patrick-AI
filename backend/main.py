from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends from fastapi.responses import StreamingResponse from starlette.middleware.cors import CORSMiddleware from pydantic import BaseModel, EmailStr from typing import List, Dict, Optional, AsyncGenerator from datetime import datetime, timedelta from jose import jwt, JWTError import os, uuid, asyncio, json

app = FastAPI() api = APIRouter(prefix="/api")

