from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import scheduler
from app.api.routes import auth, candidatures, cv, lettres, offres
from app.config import settings
from app.core.limiter import limiter
from app.db.session import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # SEC-10: fail fast if the default dev secret is still in use in production
    if settings.app_env == "production" and settings.secret_key == "dev-secret-change-me":
        raise RuntimeError(
            "SECRET_KEY is set to the default dev value. "
            "Set a secure random SECRET_KEY in your .env before starting in production."
        )
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

if settings.app_env == "production":
    app.docs_url = None
    app.redoc_url = None

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)
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
