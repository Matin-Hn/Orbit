from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List
import uuid
from app.services.object_storage import storage_service

router = APIRouter(prefix="/videos", tags=["videos"])

@router.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    """Upload a short video"""
    # Validate file type
    if not file.content_type.startswith("video/"):
        raise HTTPException(400, "File must be a video")
    
    # Validate file size (e.g., 100MB max)
    file.file.seek(0, 2)  # Seek to end
    size = file.file.tell()
    file.file.seek(0)  # Reset to beginning
    
    if size > 100 * 1024 * 1024:  # 100MB
        raise HTTPException(400, "Video too large. Max 100MB")
    
    # Generate unique filename
    file_extension = file.filename.split(".")[-1]
    unique_filename = f"videos/{uuid.uuid4()}.{file_extension}"
    
    # Upload to storage
    try:
        url = await storage_service.upload_video(file, unique_filename)
        return {
            "message": "Video uploaded successfully",
            "filename": unique_filename,
            "url": url,
            "expires_in": 3600
        }
    except Exception as e:
        raise HTTPException(500, f"Upload failed: {str(e)}")

@router.delete("/{filename}")
async def delete_video(filename: str):
    """Delete a video"""
    success = await storage_service.delete_video(filename)
    if not success:
        raise HTTPException(404, "Video not found")
    return {"message": "Video deleted successfully"}

@router.get("/{filename}/url")
async def get_video_url(filename: str, expires_in: int = 3600):
    """Get presigned URL for a video"""
    try:
        url = await storage_service.get_video_url(filename, expires_in)
        return {"url": url, "expires_in": expires_in}
    except Exception as e:
        raise HTTPException(404, f"Video not found: {str(e)}")