# app/crud/comment.py
from typing import List, Optional, Tuple, Literal
from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comment import Comment
from app.schemas.comment import CommentCreate, CommentUpdate


class CRUDComment:
    def __init__(self, model=Comment):
        self.model = model

    async def get(self, db: AsyncSession, id: int) -> Optional[Comment]:
        result = await db.execute(
            select(self.model).filter(
                and_(
                    self.model.id == id,
                    self.model.deleted_at.is_(None)
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_video(
        self,
        db: AsyncSession,
        *,
        video_id: int,
        skip: int = 0,
        limit: int = 20,
        sort_by: Literal["newest", "popular"] = "newest"
    ) -> Tuple[List[Comment], int]:
        base_filter = and_(
            self.model.video_id == video_id,
            self.model.deleted_at.is_(None),
            self.model.parent_id.is_(None)
        )

        total_result = await db.execute(
            select(func.count()).select_from(self.model).filter(base_filter)
        )
        total = total_result.scalar_one()

        if sort_by == "newest":
            # Pinned comments first, then newest
            result = await db.execute(
                select(self.model)
                .filter(base_filter)
                .order_by(
                    self.model.is_pinned.desc(),
                    self.model.created_at.desc()
                )
                .offset(skip).limit(limit)
            )
            comments = result.scalars().all()

        elif sort_by == "popular":
            # Pinned first, then by reply count (most replies = most popular)
            from sqlalchemy.orm import aliased
            Reply = aliased(self.model)

            reply_count_subquery = (
                select(
                    self.model.id,
                    func.count(Reply.id).label('reply_count')
                )
                .outerjoin(Reply, Reply.parent_id == self.model.id)
                .filter(base_filter)
                .group_by(self.model.id)
                .subquery()
            )
            result = await db.execute(
                select(self.model)
                .filter(base_filter)
                .outerjoin(
                    reply_count_subquery,
                    self.model.id == reply_count_subquery.c.id
                ).order_by(
                    self.model.is_pinned.desc(),
                    desc(func.coalesce(reply_count_subquery.c.reply_count, 0)),
                    self.model.created_at.desc()
                ).offset(skip).limit(limit)
            )
            comments = result.scalars().all()

        return comments, total

    async def get_replies(
        self,
        db: AsyncSession,
        *,
        parent_id: int,
        skip: int = 0,
        limit: int = 10
    ) -> Tuple[List[Comment], int]:
        base_filter = and_(
            self.model.parent_id == parent_id,
            self.model.deleted_at.is_(None)
        )

        total_result = await db.execute(
            select(func.count()).select_from(self.model).filter(base_filter)
        )
        total = total_result.scalar_one()

        result = await db.execute(
            select(self.model)
            .filter(base_filter)
            .order_by(self.model.created_at.asc())
            .offset(skip).limit(limit)
        )
        replies = result.scalars().all()

        return replies, total

    async def create(self, db: AsyncSession, *, obj_in: CommentCreate, user_id: int) -> Comment:
        db_obj = self.model(
            user_id=user_id,
            video_id=obj_in.video_id,
            body=obj_in.body,
            parent_id=obj_in.parent_id,
            is_approved=False  # New comments need approval by default
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: Comment,
        obj_in: CommentUpdate
    ) -> Comment:
        update_data = obj_in.dict(exclude_unset=True)

        if 'body' in update_data:
            db_obj.body = update_data['body']
            db_obj.is_edited = True

        if 'is_pinned' in update_data:
            db_obj.is_pinned = update_data['is_pinned']

        if 'is_approved' in update_data:
            db_obj.is_approved = update_data['is_approved']

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def soft_delete(self, db: AsyncSession, *, comment: Comment) -> Comment:
        comment.deleted_at = func.now()
        db.add(comment)
        await db.commit()
        await db.refresh(comment)
        return comment

    async def approve_comment(self, db: AsyncSession, *, comment: Comment) -> Comment:
        comment.is_approved = True
        db.add(comment)
        await db.commit()
        await db.refresh(comment)
        return comment

comment = CRUDComment(Comment)