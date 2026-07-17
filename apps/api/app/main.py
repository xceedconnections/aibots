from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import auth, bots, dashboard, webhooks

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title=settings.app_name,
    description="Self-hosted VICIdial AI Voice Bot Platform",
    version="1.0.0",
    lifespan=lifespan,
)

# JWT is sent via Authorization header (not cookies), so credentials=False
# is fine and allows any portal origin / IP without NetworkError.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(bots.router)
app.include_router(webhooks.router)
app.include_router(dashboard.router)


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}
