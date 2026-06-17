from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import Optional, List, Tuple
from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryUpdate


class CategoryCRUD:

    @staticmethod
    async def create(db: AsyncSession, category_in: CategoryCreate) -> Category:
        """Create a new category"""
        db_category = Category(
            name=category_in.name,
            slug=category_in.slug,
            icon_url=str(category_in.icon_url) if category_in.icon_url else None,
            description=category_in.description
        )
        db.add(db_category)
        await db.commit()
        await db.refresh(db_category)
        return db_category

    @staticmethod
    async def get(db: AsyncSession, category_id: int) -> Optional[Category]:
        """Get category by ID"""
        result = await db.execute(select(Category).filter(Category.id == category_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_slug(db: AsyncSession, slug: str) -> Optional[Category]:
        """Get category by slug"""
        result = await db.execute(select(Category).filter(Category.slug == slug))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_name(db: AsyncSession, name: str) -> Optional[Category]:
        """Get category by name"""
        result = await db.execute(select(Category).filter(Category.name == name))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_multi(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None
    ) -> Tuple[List[Category], int]:
        """Get multiple categories with pagination and search"""
        query = select(Category)
        count_query = select(func.count()).select_from(Category)

        if search:
            search_filter = or_(
                Category.name.ilike(f"%{search}%"),
                Category.description.ilike(f"%{search}%")
            )
            query = query.filter(search_filter)
            count_query = count_query.filter(search_filter)

        total = (await db.execute(count_query)).scalar_one()
        result = await db.execute(query.offset(skip).limit(limit))
        categories = result.scalars().all()

        return categories, total

    @staticmethod
    async def update(db: AsyncSession, category_id: int, category_in: CategoryUpdate) -> Optional[Category]:
        """Update a category"""
        db_category = await CategoryCRUD.get(db, category_id)
        if not db_category:
            return None

        update_data = category_in.model_dump(exclude_unset=True)

        if 'icon_url' in update_data and update_data['icon_url']:
            update_data['icon_url'] = str(update_data['icon_url'])

        for field, value in update_data.items():
            setattr(db_category, field, value)

        await db.commit()
        await db.refresh(db_category)
        return db_category

    @staticmethod
    async def delete(db: AsyncSession, category_id: int) -> bool:
        """Delete a category"""
        db_category = await CategoryCRUD.get(db, category_id)
        if not db_category:
            return False

        await db.delete(db_category)
        await db.commit()
        return True

    @staticmethod
    async def exists(db: AsyncSession, category_id: int) -> bool:
        """Check if category exists"""
        return await CategoryCRUD.get(db, category_id) is not None

    @staticmethod
    async def exists_by_name(db: AsyncSession, name: str, exclude_id: Optional[int] = None) -> bool:
        """Check if category name exists"""
        query = select(Category).filter(Category.name == name)
        if exclude_id:
            query = query.filter(Category.id != exclude_id)
        result = await db.execute(query)
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def exists_by_slug(db: AsyncSession, slug: str, exclude_id: Optional[int] = None) -> bool:
        """Check if category slug exists"""
        query = select(Category).filter(Category.slug == slug)
        if exclude_id:
            query = query.filter(Category.id != exclude_id)
        result = await db.execute(query)
        return result.scalar_one_or_none() is not None


# Initialize CRUD instance
category_crud = CategoryCRUD()