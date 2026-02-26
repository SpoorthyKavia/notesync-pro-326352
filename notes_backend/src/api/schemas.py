from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Human-readable error message.")


class SignupRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address.")
    password: str = Field(..., min_length=8, description="User password (min 8 chars).")


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address.")
    password: str = Field(..., description="User password.")


class AuthResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token.")
    token_type: str = Field("bearer", description="Token type (always 'bearer').")
    expires_at: int = Field(..., description="Unix timestamp (seconds) when token expires.")


class MeResponse(BaseModel):
    id: str = Field(..., description="User ID (UUID).")
    email: EmailStr = Field(..., description="User email address.")
    created_at: datetime = Field(..., description="Account creation timestamp.")


class TagCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, description="Tag name (unique per user).")


class TagResponse(BaseModel):
    id: str = Field(..., description="Tag ID (UUID).")
    name: str = Field(..., description="Tag name.")
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


class NoteCreateRequest(BaseModel):
    title: str = Field("", max_length=200, description="Note title.")
    content: str = Field("", description="Note content/body.")
    tag_ids: List[str] = Field(default_factory=list, description="List of tag IDs to attach.")
    pinned: bool = Field(False, description="Whether note is pinned.")
    favorited: bool = Field(False, description="Whether note is favorited.")


class NoteUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=200, description="New title.")
    content: Optional[str] = Field(None, description="New content.")
    tag_ids: Optional[List[str]] = Field(None, description="Replace tags with provided IDs.")
    pinned: Optional[bool] = Field(None, description="Set pinned state.")
    favorited: Optional[bool] = Field(None, description="Set favorited state.")
    expected_version: Optional[int] = Field(
        None,
        description="Optimistic concurrency: if set, update only if current version matches; else 409.",
    )


class NoteResponse(BaseModel):
    id: str = Field(..., description="Note ID (UUID).")
    title: str = Field(..., description="Title.")
    content: str = Field(..., description="Content.")
    pinned: bool = Field(..., description="Pinned state.")
    favorited: bool = Field(..., description="Favorited state.")
    version: int = Field(..., description="Monotonic version number (increments on each write).")
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Update timestamp.")
    tag_ids: List[str] = Field(default_factory=list, description="Attached tag IDs.")


class NotesListResponse(BaseModel):
    notes: List[NoteResponse] = Field(default_factory=list, description="List of notes.")
    server_time: datetime = Field(..., description="Current server time.")


class NotesSyncResponse(BaseModel):
    """
    Minimal sync response: return notes updated since client_last_sync.

    This supports "pull" semantics; client merges by note.version/updated_at.
    """

    notes: List[NoteResponse] = Field(default_factory=list, description="Notes updated since last sync.")
    deleted_note_ids: List[str] = Field(default_factory=list, description="IDs of notes deleted since last sync.")
    server_time: datetime = Field(..., description="Current server time.")


class NotesSearchResponse(BaseModel):
    notes: List[NoteResponse] = Field(default_factory=list, description="Matching notes.")
    server_time: datetime = Field(..., description="Current server time.")
