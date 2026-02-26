from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes_auth import router as auth_router
from src.api.routes_notes import router as notes_router
from src.api.routes_tags import router as tags_router
from src.core.settings import settings

openapi_tags = [
    {"name": "health", "description": "Service health and diagnostics."},
    {"name": "auth", "description": "Signup/login and user session endpoints."},
    {"name": "notes", "description": "Notes CRUD, pin/favorite, search, and sync endpoints."},
    {"name": "tags", "description": "Tag management endpoints."},
]

app = FastAPI(
    title="Notesync Pro Backend",
    description="Backend API for Notesync Pro (auth, notes, tags, sync).",
    version="1.0.0",
    openapi_tags=openapi_tags,
)

# CORS: allow frontend origin(s) configured via CORS_ALLOW_ORIGINS="http://localhost:3000,https://..."
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["health"], summary="Health check", description="Basic health check endpoint.")
def health_check():
    return {"message": "Healthy"}


app.include_router(auth_router)
app.include_router(tags_router)
app.include_router(notes_router)
