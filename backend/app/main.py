from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import batch, negotiations, stats, ws

app = FastAPI(title="Term Sheet Negotiation Simulator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}


app.include_router(negotiations.router)
app.include_router(batch.router)
app.include_router(stats.router)
app.include_router(ws.router)
