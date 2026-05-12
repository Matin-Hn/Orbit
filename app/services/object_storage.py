import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import UploadFile
from app.core.config import settings

class StorageService:
    def __init__(self):
        """Initialize S3 client once when service is created"""
        self.client = boto3.client(
            's3',
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            config=Config(signature_version='s3v4'),
            use_ssl=settings.S3_USE_SSL
        )
        self.bucket_name = settings.S3_BUCKET_NAME
    
    async def upload_video(self, file: UploadFile, filename: str) -> str:
        """Upload video file and return presigned URL"""
        try:
            # Upload file object directly to S3
            self.client.upload_fileobj(
                file.file,
                self.bucket_name,
                filename,
                ExtraArgs={'ContentType': 'video/mp4'}
            )
            
            # Generate presigned URL for access (valid for 1 hour)
            url = self.client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': filename
                },
                ExpiresIn=3600
            )
            return url
        
        except ClientError as e:
            raise Exception(f"Failed to upload video: {str(e)}")
    
    async def delete_video(self, filename: str) -> bool:
        """Delete video from storage"""
        try:
            self.client.delete_object(
                Bucket=self.bucket_name,
                Key=filename
            )
            return True
        except ClientError as e:
            print(f"Error deleting {filename}: {e}")
            return False
    
    async def get_video_url(self, filename: str, expires_in: int = 3600) -> str:
        """Generate presigned URL for existing video"""
        try:
            url = self.client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': filename
                },
                ExpiresIn=expires_in
            )
            return url
        except ClientError as e:
            raise Exception(f"Failed to generate URL: {str(e)}")

# Create a singleton instance
storage_service = StorageService()