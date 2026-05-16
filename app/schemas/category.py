from pydantic import BaseModel, Field, HttpUrl, validator
from typing import Optional
from datetime import datetime
import re

class CategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Category name")
    slug: Optional[str] = Field(None, min_length=1, max_length=100, description="URL-friendly slug")
    icon_url: Optional[HttpUrl] = Field(None, max_length=500, description="Category icon URL")
    description: Optional[str] = Field(None, max_length=1000, description="Category description")
    
    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('Name cannot be empty or whitespace only')
        return v.strip()
    
    @validator('slug', always=True)
    def generate_slug(cls, v, values):
        if v is None and 'name' in values:
            # Generate slug from name
            slug = values['name'].lower().strip()
            slug = re.sub(r'[^\w\s-]', '', slug)  # Remove special chars
            slug = re.sub(r'[\s_-]+', '-', slug)  # Replace spaces with hyphens
            slug = re.sub(r'^-+|-+$', '', slug)   # Remove leading/trailing hyphens
            return slug
        if v is not None:
            v = v.lower().strip()
            v = re.sub(r'[^\w\s-]', '', v)
            v = re.sub(r'[\s_-]+', '-', v)
            v = re.sub(r'^-+|-+$', '', v)
            return v
        return v

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    slug: Optional[str] = Field(None, min_length=1, max_length=100)
    icon_url: Optional[HttpUrl] = Field(None, max_length=500)
    description: Optional[str] = Field(None, max_length=1000)
    
    @validator('name')
    def validate_name(cls, v):
        if v is not None and not v.strip():
            raise ValueError('Name cannot be empty or whitespace only')
        return v.strip() if v else v
    
    @validator('slug')
    def validate_slug(cls, v):
        if v is not None:
            v = v.lower().strip()
            v = re.sub(r'[^\w\s-]', '', v)
            v = re.sub(r'[\s_-]+', '-', v)
            v = re.sub(r'^-+|-+$', '', v)
            return v
        return v

class CategoryResponse(CategoryBase):
    id: int
    name: str
    slug: str
    icon_url: Optional[str] = None
    description: Optional[str] = None
    
    class Config:
        from_attributes = True  # Pydantic v2 (formerly orm_mode)

class CategoryListResponse(BaseModel):
    items: list[CategoryResponse]
    total: int
    page: int
    size: int
    pages: int