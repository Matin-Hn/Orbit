from typing import Dict

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
        self.public_client = boto3.client(
            's3',
            endpoint_url=settings.S3_PUBLIC_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            config=Config(signature_version='s3v4'),
            use_ssl=False  # Usually false for local MinIO
        )
        self.bucket_name = settings.S3_BUCKET_NAME
        self.public_endpoint = settings.S3_PUBLIC_ENDPOINT  # For browser URLs

    async def generate_presigned_put_url(
        self, 
        object_key: str, 
        expiration: int = 3600, 
        content_type: str = "video/mp4"
    ) -> str:
        """Generate presigned URL and replace internal endpoint with public one for browser access"""
        url = self.public_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket_name, 
                "Key": object_key, 
                "ContentType": content_type
            },
            ExpiresIn=expiration
        )
        
        # Replace internal endpoint with public endpoint for browser
        internal_url = settings.S3_ENDPOINT
        if not internal_url.startswith('http'):
            internal_url = f"http://{internal_url}"
        
        return url.replace(internal_url, self.public_endpoint)

    async def object_exists(self, object_key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=object_key)
            return True
        except ClientError:
            return False
        
    def download_file(self, object_key: str, local_path: str):
        self.client.download_file(self.bucket_name, object_key, local_path)

    
    def upload_file(self, local_path: str, object_key: str, content_type: str = None):
        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type
        self.client.upload_file(local_path, self.bucket_name, object_key, ExtraArgs=extra_args)

    def get_public_url(self, object_key: str) -> str:
        # For MinIO with path-style, construct URL
        # Use the public endpoint (e.g., http://localhost:9000)
        return f"{self.public_endpoint}/{self.bucket_name}/{object_key}"

    # ... other methods (generate_upload_presigned_post, etc.) remain

    def generate_presigned_get_url(self, object_key: str, expiration: int = 60) -> str:
        """
        Generate a presigned GET URL for an S3 object.
        Used for secure, short-lived access to the HLS manifest.
        """
        url = self.public_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.bucket_name, 'Key': object_key},
            ExpiresIn=expiration
        )
        # Ensure the URL uses the public endpoint (replace internal if needed)
        internal_url = settings.S3_ENDPOINT
        if not internal_url.startswith('http'):
            internal_url = f"http://{internal_url}"
        return url.replace(internal_url, self.public_endpoint)

storage_service = StorageService()