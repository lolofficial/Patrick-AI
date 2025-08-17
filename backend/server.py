from fastapi import FastAPI, APIRouter from starlette.middleware.cors import CORSMiddleware import os

app = FastAPI()

api_router = APIRouter(prefix="/api")

@api_router.get("/") async def hello(): return {"message": "Hello World"}

app.include_router(api_router)

CORS minimale: per il test non usiamo credenziali
cors_env = os.environ.get("CORS_ORIGINS", "") origins = [o.strip() for o in cors_env.split(",") if o.strip()] if not origins: origins = ["*"]

app.add_middleware( CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=[""], allow_headers=[""], )
