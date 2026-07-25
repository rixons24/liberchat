from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, posts, dm, media, reports, moderation, admin_auth
from app.workers.cleanup import start_background_workers

app = FastAPI(title="LiberChat API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your real frontend origin(s) before launch
    allow_methods=["*"],
    allow_headers=["*"],
)

# Schema is managed by Alembic migrations (see /alembic). Run
# `alembic upgrade head` before starting the app — this no longer
# auto-creates tables, so a fresh/incomplete schema will surface as a
# clear DB error rather than silently drifting from migration history.

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(posts.router, prefix="/posts", tags=["posts"])
app.include_router(dm.router, prefix="/dm", tags=["dm"])
app.include_router(media.router, prefix="/media", tags=["media"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])
app.include_router(moderation.router, prefix="/mod", tags=["moderation"])
app.include_router(admin_auth.router, prefix="/admin", tags=["admin"])


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.on_event("startup")
async def startup():
    await start_background_workers()
