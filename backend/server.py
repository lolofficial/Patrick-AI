from fastapi import FastAPI, APIRouter, HTTPException, Path, Body, Request, Depends from fastapi.responses import StreamingResponse, JSONResponse from starlette.middleware.cors import CORSMiddleware from motor.motor_asyncio import AsyncIOMotorClient from pydantic import BaseModel, Field, EmailStr from typing import List, Optional, Literal, AsyncGenerator from datetime import datetime, timedelta from jose import jwt, JWTError from passlib.hash import bcrypt import os, uuid, asyncio, json, logging, requests


