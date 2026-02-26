from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.api.deps import AuthenticatedUser, get_current_user
from src.api.schemas import TagCreateRequest, TagResponse
from src.db.repo import Repo
from src.db.session import get_db_session

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get(
    "",
    response_model=list[TagResponse],
    summary="List tags",
    description="List all tags for the current user.",
)
async def list_tags(user: AuthenticatedUser = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)) -> list[TagResponse]:
    repo = Repo(db)
    tags = await repo.list_tags(user_id=user.user_id)
    return [TagResponse(id=t.id, name=t.name, created_at=t.created_at, updated_at=t.updated_at) for t in tags]


@router.post(
    "",
    response_model=TagResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create tag",
    description="Create a new tag for the current user.",
)
async def create_tag(
    payload: TagCreateRequest, user: AuthenticatedUser = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)
) -> TagResponse:
    repo = Repo(db)
    try:
        tag = await repo.create_tag(user_id=user.user_id, name=payload.name.strip())
    except IntegrityError:
        # Unique constraint on (user_id, name) expected.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tag name already exists.")
    return TagResponse(id=tag.id, name=tag.name, created_at=tag.created_at, updated_at=tag.updated_at)


@router.delete(
    "/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete tag",
    description="Delete a tag by id. Note/tag associations are also removed.",
)
async def delete_tag(tag_id: str, user: AuthenticatedUser = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)) -> None:
    repo = Repo(db)
    await repo.delete_tag(user_id=user.user_id, tag_id=tag_id)
    return None
