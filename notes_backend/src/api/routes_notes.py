from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.api.deps import AuthenticatedUser, get_current_user
from src.api.schemas import (
    NoteCreateRequest,
    NoteResponse,
    NoteUpdateRequest,
    NotesListResponse,
    NotesSearchResponse,
    NotesSyncResponse,
)
from src.db.repo import Repo
from src.db.session import get_db_session

router = APIRouter(prefix="/notes", tags=["notes"])


def _note_to_response(note, tag_ids: list[str]) -> NoteResponse:
    return NoteResponse(
        id=note.id,
        title=note.title,
        content=note.content,
        pinned=note.pinned,
        favorited=note.favorited,
        version=note.version,
        created_at=note.created_at,
        updated_at=note.updated_at,
        tag_ids=tag_ids,
    )


@router.get(
    "",
    response_model=NotesListResponse,
    summary="List notes",
    description="List notes for the current user. Optionally filter by tag_id.",
)
async def list_notes(
    tag_id: Optional[str] = Query(None, description="Optional tag id to filter notes."),
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> NotesListResponse:
    repo = Repo(db)
    notes = await repo.list_notes(user_id=user.user_id, tag_id=tag_id)
    out: list[NoteResponse] = []
    for n in notes:
        tag_ids = await repo.get_note_tag_ids(user_id=user.user_id, note_id=n.id)
        out.append(_note_to_response(n, tag_ids))
    return NotesListResponse(notes=out, server_time=datetime.now(timezone.utc))


@router.post(
    "",
    response_model=NoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create note",
    description="Create a new note with optional tags and pinned/favorited state.",
)
async def create_note(
    payload: NoteCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> NoteResponse:
    repo = Repo(db)
    note = await repo.create_note(
        user_id=user.user_id,
        title=payload.title,
        content=payload.content,
        pinned=payload.pinned,
        favorited=payload.favorited,
        tag_ids=payload.tag_ids,
    )
    tag_ids = await repo.get_note_tag_ids(user_id=user.user_id, note_id=note.id)
    return _note_to_response(note, tag_ids)


@router.get(
    "/{note_id}",
    response_model=NoteResponse,
    summary="Get note",
    description="Get a single note by id.",
)
async def get_note(note_id: str, user: AuthenticatedUser = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)) -> NoteResponse:
    repo = Repo(db)
    note = await repo.get_note(user_id=user.user_id, note_id=note_id)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found.")
    tag_ids = await repo.get_note_tag_ids(user_id=user.user_id, note_id=note.id)
    return _note_to_response(note, tag_ids)


@router.patch(
    "/{note_id}",
    response_model=NoteResponse,
    summary="Update note",
    description="Update a note. Supports optimistic concurrency via expected_version.",
)
async def update_note(
    note_id: str,
    payload: NoteUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> NoteResponse:
    repo = Repo(db)
    updated = await repo.update_note(
        user_id=user.user_id,
        note_id=note_id,
        title=payload.title,
        content=payload.content,
        pinned=payload.pinned,
        favorited=payload.favorited,
        tag_ids=payload.tag_ids,
        expected_version=payload.expected_version,
    )
    if updated is None:
        # Distinguish not found vs version conflict
        existing = await repo.get_note(user_id=user.user_id, note_id=note_id)
        if existing is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found.")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Version conflict (note updated elsewhere).")

    tag_ids = await repo.get_note_tag_ids(user_id=user.user_id, note_id=note_id)
    return _note_to_response(updated, tag_ids)


@router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete note",
    description="Delete a note and its tag associations.",
)
async def delete_note(note_id: str, user: AuthenticatedUser = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)) -> None:
    repo = Repo(db)
    await repo.delete_note(user_id=user.user_id, note_id=note_id)
    return None


@router.get(
    "/search",
    response_model=NotesSearchResponse,
    summary="Search notes",
    description="Search notes by query in title/content (ILIKE). Returns up to 100 results.",
)
async def search_notes(
    q: str = Query(..., min_length=1, description="Search query."),
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> NotesSearchResponse:
    repo = Repo(db)
    notes = await repo.search_notes(user_id=user.user_id, query=q)
    out: list[NoteResponse] = []
    for n in notes:
        tag_ids = await repo.get_note_tag_ids(user_id=user.user_id, note_id=n.id)
        out.append(_note_to_response(n, tag_ids))
    return NotesSearchResponse(notes=out, server_time=datetime.now(timezone.utc))


@router.get(
    "/sync/pull",
    response_model=NotesSyncResponse,
    summary="Sync pull",
    description=(
        "Pull notes updated since a given timestamp. Client merges by version/updated_at. "
        "Deleted note tracking requires a tombstone table; if schema doesn't have it, deleted_note_ids is empty."
    ),
)
async def sync_pull(
    since: Optional[datetime] = Query(None, description="Return notes updated after this timestamp (UTC)."),
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> NotesSyncResponse:
    # Without a dedicated tombstone table, we can only return updated notes.
    # This keeps contract stable while allowing future enhancement.
    repo = Repo(db)

    if since is None:
        notes = await repo.list_notes(user_id=user.user_id, tag_id=None)
    else:
        result = await db.execute(
            text(
                """
                SELECT id, title, content, pinned, favorited, version, created_at, updated_at
                FROM notes
                WHERE user_id = :user_id AND updated_at > :since
                ORDER BY updated_at DESC
                """
            ),
            {"user_id": user.user_id, "since": since},
        )
        rows = [dict(r._mapping) for r in result.fetchall()]
        notes = [
            type(
                "TmpNote",
                (),
                {
                    "id": str(r["id"]),
                    "title": r["title"],
                    "content": r["content"],
                    "pinned": r["pinned"],
                    "favorited": r["favorited"],
                    "version": r["version"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                },
            )()
            for r in rows
        ]

    out: list[NoteResponse] = []
    for n in notes:
        tag_ids = await repo.get_note_tag_ids(user_id=user.user_id, note_id=n.id)
        out.append(
            NoteResponse(
                id=n.id,
                title=n.title,
                content=n.content,
                pinned=n.pinned,
                favorited=n.favorited,
                version=n.version,
                created_at=n.created_at,
                updated_at=n.updated_at,
                tag_ids=tag_ids,
            )
        )

    return NotesSyncResponse(notes=out, deleted_note_ids=[], server_time=datetime.now(timezone.utc))
