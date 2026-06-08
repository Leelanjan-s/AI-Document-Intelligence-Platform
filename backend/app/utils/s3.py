import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
import asyncio
import os
from typing import Optional
from app.core.config import settings
from loguru import logger

class S3Storage:
    def __init__(self):
        # Configure Boto3 client to speak to MinIO
        self.endpoint_url = f"http://{settings.MINIO_ENDPOINT}" if not settings.MINIO_ENDPOINT.startswith("http") else settings.MINIO_ENDPOINT
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            config=Config(
                signature_version="s3v4",
                connect_timeout=1,  # Fast timeout to allow instant local fallback
                read_timeout=1
            ),
            region_name="us-east-1"
        )
        self.bucket_name = settings.MINIO_BUCKET
        self.use_local = False
        self.local_dir = None

    def _ensure_local_dir(self) -> None:
        if not self.local_dir:
            self.local_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "local_storage"))
        os.makedirs(self.local_dir, exist_ok=True)
        logger.info(f"Local storage fallback initialized at: {self.local_dir}")

    def _get_doc_id_from_object_name(self, object_name: str) -> str:
        base = os.path.basename(object_name)
        doc_id = base.split(".")[0]
        return doc_id

    def ensure_bucket_exists(self) -> None:
        """Initialize the storage bucket if it does not already exist."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"S3 bucket '{self.bucket_name}' already exists.")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code in ["404", "NoSuchBucket"]:
                logger.info(f"S3 bucket '{self.bucket_name}' not found. Creating bucket...")
                self.s3_client.create_bucket(Bucket=self.bucket_name)
                logger.info(f"S3 bucket '{self.bucket_name}' created successfully.")
            else:
                logger.error(f"Error checking bucket existence: {e}. Falling back to local storage.")
                self.use_local = True
                self._ensure_local_dir()
        except Exception as e:
            logger.error(f"Failed to check S3 bucket: {e}. Falling back to local storage.")
            self.use_local = True
            self._ensure_local_dir()

    async def get_presigned_upload_url(self, object_name: str, expiration: int = 3600) -> str:
        """Generate a presigned URL for direct client-side upload."""
        if self.use_local:
            doc_id = self._get_doc_id_from_object_name(object_name)
            return f"http://localhost:8000/documents/{doc_id}/file"
        return await asyncio.to_thread(
            self._generate_presigned_url, "put_object", object_name, expiration
        )

    async def get_presigned_download_url(self, object_name: str, expiration: int = 3600) -> str:
        """Generate a presigned URL for authenticated download access."""
        if self.use_local:
            doc_id = self._get_doc_id_from_object_name(object_name)
            return f"http://localhost:8000/documents/{doc_id}/file"
        return await asyncio.to_thread(
            self._generate_presigned_url, "get_object", object_name, expiration
        )

    def _generate_presigned_url(self, client_method: str, object_name: str, expiration: int) -> str:
        try:
            url = self.s3_client.generate_presigned_url(
                ClientMethod=client_method,
                Params={"Bucket": self.bucket_name, "Key": object_name},
                ExpiresIn=expiration,
            )
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise

    async def upload_file_bytes(self, object_name: str, data: bytes, content_type: str) -> None:
        """Upload raw byte stream directly into S3 storage or local disk."""
        if self.use_local:
            self._ensure_local_dir()
            file_path = os.path.join(self.local_dir, object_name)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            await asyncio.to_thread(self._write_local_file, file_path, data)
            logger.info(f"Uploaded {object_name} to local storage path {file_path}")
            return

        await asyncio.to_thread(
            self.s3_client.put_object,
            Bucket=self.bucket_name,
            Key=object_name,
            Body=data,
            ContentType=content_type
        )
        logger.info(f"Uploaded {object_name} to bucket {self.bucket_name}")

    def _write_local_file(self, path: str, data: bytes) -> None:
        with open(path, "wb") as f:
            f.write(data)

    async def download_file_bytes(self, object_name: str) -> bytes:
        """Fetch file binary data directly from storage or local disk."""
        if self.use_local:
            self._ensure_local_dir()
            file_path = os.path.join(self.local_dir, object_name)
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Local file {file_path} not found")
            return await asyncio.to_thread(self._read_local_file, file_path)

        response = await asyncio.to_thread(
            self.s3_client.get_object,
            Bucket=self.bucket_name,
            Key=object_name
        )
        return await asyncio.to_thread(response["Body"].read)

    def _read_local_file(self, path: str) -> bytes:
        with open(path, "rb") as f:
            return f.read()

    async def delete_file(self, object_name: str) -> None:
        """Delete file from S3 storage bucket or local disk."""
        if self.use_local:
            self._ensure_local_dir()
            file_path = os.path.join(self.local_dir, object_name)
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Deleted local storage file {file_path}")
                else:
                    logger.warning(f"Local storage file {file_path} does not exist")
            except Exception as e:
                logger.error(f"Failed to delete local file {file_path}: {e}")
            return

        try:
            await asyncio.to_thread(
                self.s3_client.delete_object,
                Bucket=self.bucket_name,
                Key=object_name
            )
            logger.info(f"Deleted {object_name} from bucket {self.bucket_name}")
        except Exception as e:
            logger.warning(f"Failed to delete S3 object {object_name}: {e}")

# Global storage instance
storage = S3Storage()
