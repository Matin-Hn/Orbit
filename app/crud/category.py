from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional, List, Tuple
from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryUpdate

class CategoryCRUD:
    
    @staticmethod
    def create(db: Session, category_in: CategoryCreate) -> Category:
        """Create a new category"""
        db_category = Category(
            name=category_in.name,
            slug=category_in.slug,
            icon_url=str(category_in.icon_url) if category_in.icon_url else None,
            description=category_in.description
        )
        db.add(db_category)
        db.commit()
        db.refresh(db_category)
        return db_category
    
    @staticmethod
    def get(db: Session, category_id: int) -> Optional[Category]:
        """Get category by ID"""
        return db.query(Category).filter(Category.id == category_id).first()
    
    @staticmethod
    def get_by_slug(db: Session, slug: str) -> Optional[Category]:
        """Get category by slug"""
        return db.query(Category).filter(Category.slug == slug).first()
    
    @staticmethod
    def get_by_name(db: Session, name: str) -> Optional[Category]:
        """Get category by name"""
        return db.query(Category).filter(Category.name == name).first()
    
    @staticmethod
    def get_multi(
        db: Session, 
        skip: int = 0, 
        limit: int = 100,
        search: Optional[str] = None
    ) -> Tuple[List[Category], int]:
        """Get multiple categories with pagination and search"""
        query = db.query(Category)
        
        if search:
            query = query.filter(
                Category.name.ilike(f"%{search}%") | 
                Category.description.ilike(f"%{search}%")
            )
        
        total = query.count()
        categories = query.offset(skip).limit(limit).all()
        
        return categories, total
    
    @staticmethod
    def update(db: Session, category_id: int, category_in: CategoryUpdate) -> Optional[Category]:
        """Update a category"""
        db_category = CategoryCRUD.get(db, category_id)
        if not db_category:
            return None
        
        update_data = category_in.model_dump(exclude_unset=True)
        
        if 'icon_url' in update_data and update_data['icon_url']:
            update_data['icon_url'] = str(update_data['icon_url'])
        
        for field, value in update_data.items():
            setattr(db_category, field, value)
        
        db.commit()
        db.refresh(db_category)
        return db_category
    
    @staticmethod
    def delete(db: Session, category_id: int) -> bool:
        """Delete a category"""
        db_category = CategoryCRUD.get(db, category_id)
        if not db_category:
            return False
        
        db.delete(db_category)
        db.commit()
        return True
    
    @staticmethod
    def exists(db: Session, category_id: int) -> bool:
        """Check if category exists"""
        return db.query(Category).filter(Category.id == category_id).first() is not None
    
    @staticmethod
    def exists_by_name(db: Session, name: str, exclude_id: Optional[int] = None) -> bool:
        """Check if category name exists"""
        query = db.query(Category).filter(Category.name == name)
        if exclude_id:
            query = query.filter(Category.id != exclude_id)
        return query.first() is not None
    
    @staticmethod
    def exists_by_slug(db: Session, slug: str, exclude_id: Optional[int] = None) -> bool:
        """Check if category slug exists"""
        query = db.query(Category).filter(Category.slug == slug)
        if exclude_id:
            query = query.filter(Category.id != exclude_id)
        return query.first() is not None

# Initialize CRUD instance
category_crud = CategoryCRUD()