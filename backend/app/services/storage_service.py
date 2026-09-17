import os
import io
import uuid
import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger("trustengine.storage")


class StorageService:
    """
    Object Storage Service Abstraction (S3 / MinIO / Local Disk).
    Provides durable, versioned artifact storage for generated PDF reports, Excel exports,
    and Evaluation benchmark JSON snapshots (REQ-STORAGE-01).
    """

    def __init__(self):
        self.backend = getattr(settings, "STORAGE_BACKEND", "local")
        self.local_dir = getattr(settings, "STORAGE_LOCAL_DIR", "storage/artifacts")
        if self.backend == "local":
            os.makedirs(self.local_dir, exist_ok=True)

    def store_artifact(
        self,
        content: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
        prefix: str = "reports",
    ) -> dict:
        """
        Stores artifact bytes and returns metadata (key, filename, content_type, size_bytes, uri).
        """
        unique_id = str(uuid.uuid4())[:8]
        file_key = f"{prefix}/{unique_id}_{filename}"

        if self.backend == "local":
            full_path = os.path.join(self.local_dir, file_key)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "wb") as f:
                f.write(content)
            
            return {
                "file_key": file_key,
                "filename": filename,
                "content_type": content_type,
                "size_bytes": len(content),
                "storage_backend": "local",
                "uri": full_path,
            }
        else:
            # S3 / MinIO integration
            try:
                import boto3
                s3_client = boto3.client(
                    "s3",
                    endpoint_url=getattr(settings, "S3_ENDPOINT_URL", None),
                    aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", None),
                    aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
                )
                bucket_name = getattr(settings, "S3_BUCKET_NAME", "trustengine-artifacts")
                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=file_key,
                    Body=content,
                    ContentType=content_type,
                )
                return {
                    "file_key": file_key,
                    "filename": filename,
                    "content_type": content_type,
                    "size_bytes": len(content),
                    "storage_backend": self.backend,
                    "uri": f"s3://{bucket_name}/{file_key}",
                }
            except Exception as e:
                logger.error(f"S3 upload failed: {e}. Falling back to local storage.")
                full_path = os.path.join(self.local_dir, file_key)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "wb") as f:
                    f.write(content)
                return {
                    "file_key": file_key,
                    "filename": filename,
                    "content_type": content_type,
                    "size_bytes": len(content),
                    "storage_backend": "local_fallback",
                    "uri": full_path,
                }

    def retrieve_artifact(self, file_key: str) -> Optional[bytes]:
        """Retrieves raw artifact content by key."""
        if self.backend == "local":
            full_path = os.path.join(self.local_dir, file_key)
            if os.path.exists(full_path):
                with open(full_path, "rb") as f:
                    return f.read()
            return None
        else:
            try:
                import boto3
                s3_client = boto3.client("s3")
                bucket_name = getattr(settings, "S3_BUCKET_NAME", "trustengine-artifacts")
                resp = s3_client.get_object(Bucket=bucket_name, Key=file_key)
                return resp["Body"].read()
            except Exception as e:
                logger.error(f"S3 retrieve error: {e}")
                return None
