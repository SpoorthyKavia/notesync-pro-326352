from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class UserRow:
    id: str
    email: str
    password_hash: str
    created_at: datetime


@dataclass(frozen=True)
class TagRow:
    id: str
    name: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class NoteRow:
    id: str
    title: str
    content: str
    pinned: bool
    favorited: bool
    version: int
    created_at: datetime
    updated_at: datetime


def _rows_to_list(result) -> list:
    return [dict(r._mapping) for r in result.fetchall()]


class Repo:
    """
    SQL repository (I/O layer).

    Notes:
    - Uses SQL text queries to match an existing schema without ORM models.
    - All methods accept an AsyncSession and never read environment variables.
    """

    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_user_by_email(self, email: str) -> Optional[UserRow]:
        result = await self._db.execute(
            text(
                """
                SELECT id, email, password_hash, created_at
                FROM users
                WHERE email = :email
                LIMIT 1
                """
            ),
            {"email": email},
        )
        row = result.first()
        if row is None:
            return None
        m = row._mapping
        return UserRow(id=str(m["id"]), email=m["email"], password_hash=m["password_hash"], created_at=m["created_at"])

    async def get_user_by_id(self, user_id: str) -> Optional[UserRow]:
        result = await self._db.execute(
            text(
                """
                SELECT id, email, password_hash, created_at
                FROM users
                WHERE id = :id
                LIMIT 1
                """
            ),
            {"id": user_id},
        )
        row = result.first()
        if row is None:
            return None
        m = row._mapping
        return UserRow(id=str(m["id"]), email=m["email"], password_hash=m["password_hash"], created_at=m["created_at"])

    async def create_user(self, *, email: str, password_hash: str) -> UserRow:
        result = await self._db.execute(
            text(
                """
                INSERT INTO users (email, password_hash)
                VALUES (:email, :password_hash)
                RETURNING id, email, password_hash, created_at
                """
            ),
            {"email": email, "password_hash": password_hash},
        )
        await self._db.commit()
        m = result.first()._mapping
        return UserRow(id=str(m["id"]), email=m["email"], password_hash=m["password_hash"], created_at=m["created_at"])

    async def create_session(self, *, user_id: str, session_token: str, expires_at: datetime) -> None:
        await self._db.execute(
            text(
                """
                INSERT INTO sessions (user_id, session_token, expires_at)
                VALUES (:user_id, :session_token, :expires_at)
                """
            ),
            {"user_id": user_id, "session_token": session_token, "expires_at": expires_at},
        )
        await self._db.commit()

    async def revoke_session(self, *, user_id: str, session_token: str) -> None:
        await self._db.execute(
            text(
                """
                UPDATE sessions
                SET revoked_at = NOW()
                WHERE user_id = :user_id AND session_token = :session_token AND revoked_at IS NULL
                """
            ),
            {"user_id": user_id, "session_token": session_token},
        )
        await self._db.commit()

    async def list_tags(self, *, user_id: str) -> List[TagRow]:
        result = await self._db.execute(
            text(
                """
                SELECT id, name, created_at, updated_at
                FROM tags
                WHERE user_id = :user_id
                ORDER BY lower(name) ASC
                """
            ),
            {"user_id": user_id},
        )
        rows = _rows_to_list(result)
        return [TagRow(id=str(r["id"]), name=r["name"], created_at=r["created_at"], updated_at=r["updated_at"]) for r in rows]

    async def create_tag(self, *, user_id: str, name: str) -> TagRow:
        result = await self._db.execute(
            text(
                """
                INSERT INTO tags (user_id, name)
                VALUES (:user_id, :name)
                RETURNING id, name, created_at, updated_at
                """
            ),
            {"user_id": user_id, "name": name},
        )
        await self._db.commit()
        m = result.first()._mapping
        return TagRow(id=str(m["id"]), name=m["name"], created_at=m["created_at"], updated_at=m["updated_at"])

    async def delete_tag(self, *, user_id: str, tag_id: str) -> None:
        # note_tags has FK; rely on ON DELETE CASCADE if set in schema, otherwise delete join first.
        await self._db.execute(
            text("DELETE FROM note_tags WHERE user_id = :user_id AND tag_id = :tag_id"),
            {"user_id": user_id, "tag_id": tag_id},
        )
        await self._db.execute(
            text("DELETE FROM tags WHERE user_id = :user_id AND id = :tag_id"),
            {"user_id": user_id, "tag_id": tag_id},
        )
        await self._db.commit()

    async def list_notes(self, *, user_id: str, tag_id: Optional[str] = None) -> List[NoteRow]:
        if tag_id:
            q = """
                SELECT n.id, n.title, n.content, n.pinned, n.favorited, n.version, n.created_at, n.updated_at
                FROM notes n
                JOIN note_tags nt ON nt.note_id = n.id
                WHERE n.user_id = :user_id AND nt.tag_id = :tag_id
                ORDER BY n.pinned DESC, n.updated_at DESC
            """
            params = {"user_id": user_id, "tag_id": tag_id}
        else:
            q = """
                SELECT id, title, content, pinned, favorited, version, created_at, updated_at
                FROM notes
                WHERE user_id = :user_id
                ORDER BY pinned DESC, updated_at DESC
            """
            params = {"user_id": user_id}

        result = await self._db.execute(text(q), params)
        rows = _rows_to_list(result)
        return [
            NoteRow(
                id=str(r["id"]),
                title=r["title"],
                content=r["content"],
                pinned=r["pinned"],
                favorited=r["favorited"],
                version=r["version"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    async def get_note(self, *, user_id: str, note_id: str) -> Optional[NoteRow]:
        result = await self._db.execute(
            text(
                """
                SELECT id, title, content, pinned, favorited, version, created_at, updated_at
                FROM notes
                WHERE user_id = :user_id AND id = :id
                LIMIT 1
                """
            ),
            {"user_id": user_id, "id": note_id},
        )
        row = result.first()
        if row is None:
            return None
        m = row._mapping
        return NoteRow(
            id=str(m["id"]),
            title=m["title"],
            content=m["content"],
            pinned=m["pinned"],
            favorited=m["favorited"],
            version=m["version"],
            created_at=m["created_at"],
            updated_at=m["updated_at"],
        )

    async def get_note_tag_ids(self, *, user_id: str, note_id: str) -> List[str]:
        result = await self._db.execute(
            text("SELECT tag_id FROM note_tags WHERE user_id = :user_id AND note_id = :note_id"),
            {"user_id": user_id, "note_id": note_id},
        )
        return [str(r._mapping["tag_id"]) for r in result.fetchall()]

    async def replace_note_tags(self, *, user_id: str, note_id: str, tag_ids: Sequence[str]) -> None:
        await self._db.execute(
            text("DELETE FROM note_tags WHERE user_id = :user_id AND note_id = :note_id"),
            {"user_id": user_id, "note_id": note_id},
        )
        for tid in tag_ids:
            await self._db.execute(
                text("INSERT INTO note_tags (user_id, note_id, tag_id) VALUES (:user_id, :note_id, :tag_id)"),
                {"user_id": user_id, "note_id": note_id, "tag_id": tid},
            )

    async def create_note(
        self,
        *,
        user_id: str,
        title: str,
        content: str,
        pinned: bool,
        favorited: bool,
        tag_ids: Sequence[str],
    ) -> NoteRow:
        result = await self._db.execute(
            text(
                """
                INSERT INTO notes (user_id, title, content, pinned, favorited)
                VALUES (:user_id, :title, :content, :pinned, :favorited)
                RETURNING id, title, content, pinned, favorited, version, created_at, updated_at
                """
            ),
            {"user_id": user_id, "title": title, "content": content, "pinned": pinned, "favorited": favorited},
        )
        note_map = result.first()._mapping
        note_id = str(note_map["id"])

        await self.replace_note_tags(user_id=user_id, note_id=note_id, tag_ids=tag_ids)
        await self._db.commit()

        return NoteRow(
            id=note_id,
            title=note_map["title"],
            content=note_map["content"],
            pinned=note_map["pinned"],
            favorited=note_map["favorited"],
            version=note_map["version"],
            created_at=note_map["created_at"],
            updated_at=note_map["updated_at"],
        )

    async def update_note(
        self,
        *,
        user_id: str,
        note_id: str,
        title: Optional[str],
        content: Optional[str],
        pinned: Optional[bool],
        favorited: Optional[bool],
        tag_ids: Optional[Sequence[str]],
        expected_version: Optional[int],
    ) -> Optional[NoteRow]:
        # optimistic concurrency control: update only if version matches
        where_version = ""
        params = {"user_id": user_id, "id": note_id, "title": title, "content": content, "pinned": pinned, "favorited": favorited}
        if expected_version is not None:
            where_version = "AND version = :expected_version"
            params["expected_version"] = expected_version

        result = await self._db.execute(
            text(
                f"""
                UPDATE notes
                SET
                  title = COALESCE(:title, title),
                  content = COALESCE(:content, content),
                  pinned = COALESCE(:pinned, pinned),
                  favorited = COALESCE(:favorited, favorited),
                  version = version + 1,
                  updated_at = NOW()
                WHERE user_id = :user_id AND id = :id
                {where_version}
                RETURNING id, title, content, pinned, favorited, version, created_at, updated_at
                """
            ),
            params,
        )
        row = result.first()
        if row is None:
            await self._db.rollback()
            return None

        if tag_ids is not None:
            await self.replace_note_tags(user_id=user_id, note_id=note_id, tag_ids=tag_ids)

        await self._db.commit()
        m = row._mapping
        return NoteRow(
            id=str(m["id"]),
            title=m["title"],
            content=m["content"],
            pinned=m["pinned"],
            favorited=m["favorited"],
            version=m["version"],
            created_at=m["created_at"],
            updated_at=m["updated_at"],
        )

    async def delete_note(self, *, user_id: str, note_id: str) -> None:
        await self._db.execute(
            text("DELETE FROM note_tags WHERE user_id = :user_id AND note_id = :note_id"),
            {"user_id": user_id, "note_id": note_id},
        )
        await self._db.execute(
            text("DELETE FROM notes WHERE user_id = :user_id AND id = :note_id"),
            {"user_id": user_id, "note_id": note_id},
        )
        await self._db.commit()

    async def search_notes(self, *, user_id: str, query: str) -> List[NoteRow]:
        result = await self._db.execute(
            text(
                """
                SELECT id, title, content, pinned, favorited, version, created_at, updated_at
                FROM notes
                WHERE user_id = :user_id
                  AND (title ILIKE :q OR content ILIKE :q)
                ORDER BY pinned DESC, updated_at DESC
                LIMIT 100
                """
            ),
            {"user_id": user_id, "q": f"%{query}%"},
        )
        rows = _rows_to_list(result)
        return [
            NoteRow(
                id=str(r["id"]),
                title=r["title"],
                content=r["content"],
                pinned=r["pinned"],
                favorited=r["favorited"],
                version=r["version"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]
