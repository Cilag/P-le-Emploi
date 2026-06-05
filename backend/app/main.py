from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.db.session import engine, Base
from app.api import scheduler
from app.api.routes import offres, lettres, candidatures, cv


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="Pôle Emploi — Assistant de Candidature",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(offres.router)
app.include_router(lettres.router)
app.include_router(candidatures.router)
app.include_router(cv.router)
app.include_router(scheduler.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "backend"}


@app.get("/")
async def root():
    return {"message": "Pôle Emploi API"}
