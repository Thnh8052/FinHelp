import shutil
from pathlib import Path
from typing import Optional
from fastapi import UploadFile
from app.core.config import settings
from app.core.logging import logger


class StorageService:
    """Manages file persistence for uploaded PDFs and parsing artifacts.

    Supports both local filesystem and Cloudflare R2 (S3-compatible) Object Storage.
    In R2 mode, files are synced to R2 while keeping a local cache for high-speed Docling processing.
    """

    def __init__(self):
        self.pdf_dir: Path = settings.PDF_STORAGE_DIR
        self.artifacts_dir: Path = settings.ARTIFACTS_STORAGE_DIR
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.backend: str = getattr(settings, "STORAGE_BACKEND", "local")
        self._s3_client = None

    @property
    def s3_client(self):
        """Lazy-loaded boto3 client for Cloudflare R2."""
        if self._s3_client is None and self.backend == "r2":
            if not settings.R2_ENDPOINT_URL or not settings.R2_ACCESS_KEY_ID or not settings.R2_SECRET_ACCESS_KEY:
                logger.warning("STORAGE_BACKEND is 'r2' but R2 credentials are not fully configured.")
                return None
            try:
                import boto3
                from botocore.config import Config

                self._s3_client = boto3.client(
                    service_name="s3",
                    endpoint_url=settings.R2_ENDPOINT_URL,
                    aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                    config=Config(signature_version="s3v4"),
                    region_name="auto",
                )
            except Exception as e:
                logger.error(f"Failed to initialize S3 client for Cloudflare R2: {e}")
                self._s3_client = None
        return self._s3_client

    async def save_pdf(self, notebook_id: str, document_id: str, file: UploadFile) -> Path:
        """Save an uploaded PDF to local disk and sync to Cloudflare R2 if enabled."""
        dest_folder = self.pdf_dir / notebook_id
        dest_folder.mkdir(parents=True, exist_ok=True)
        dest_path = dest_folder / f"{document_id}_{Path(file.filename).name}"

        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        logger.info(f"Saved PDF to local cache: {dest_path}")

        # Sync to Cloudflare R2
        if self.backend == "r2" and self.s3_client:
            s3_key = f"pdfs/{notebook_id}/{dest_path.name}"
            try:
                self.s3_client.upload_file(
                    Filename=str(dest_path),
                    Bucket=settings.R2_BUCKET_NAME,
                    Key=s3_key,
                    ExtraArgs={"ContentType": "application/pdf"},
                )
                logger.info(f"Synced PDF to Cloudflare R2: {settings.R2_BUCKET_NAME}/{s3_key}")
            except Exception as e:
                logger.error(f"Failed to sync PDF to Cloudflare R2: {e}")

        return dest_path

    def get_pdf_path(self, notebook_id: str, document_id: str, filename: str) -> Path:
        """Return the local path to the PDF. If missing locally, pull from R2 on demand."""
        dest_path = self.pdf_dir / notebook_id / f"{document_id}_{Path(filename).name}"

        # If file is not present locally and R2 is enabled, pull from R2
        if not dest_path.is_file() and self.backend == "r2" and self.s3_client:
            s3_key = f"pdfs/{notebook_id}/{dest_path.name}"
            try:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                logger.info(f"Pulling PDF from R2 to local cache: {s3_key} -> {dest_path}")
                self.s3_client.download_file(
                    Bucket=settings.R2_BUCKET_NAME,
                    Key=s3_key,
                    Filename=str(dest_path),
                )
            except Exception as e:
                logger.warning(f"Could not download PDF from R2: {e}")

        return dest_path

    def delete_notebook_folder(self, notebook_id: str) -> None:
        """Remove the notebook's PDF folder once its documents are gone."""
        shutil.rmtree(self.pdf_dir / notebook_id, ignore_errors=True)

    def get_public_pdf_url(self, notebook_id: str, document_id: str, filename: str) -> Optional[str]:
        """Return the public Cloudflare CDN URL for direct browser viewing (0$ egress)."""
        if self.backend == "r2" and settings.R2_PUBLIC_DOMAIN:
            clean_name = f"{document_id}_{Path(filename).name}"
            return f"{settings.R2_PUBLIC_DOMAIN.rstrip('/')}/pdfs/{notebook_id}/{clean_name}"
        return None

    def sync_artifacts_to_r2(self, document_id: str) -> None:
        """Sync a parsed document's artifacts directory to Cloudflare R2."""
        if self.backend != "r2" or not self.s3_client:
            return

        artifact_dir = self.artifacts_dir / document_id
        if not artifact_dir.is_dir():
            return

        try:
            for item in artifact_dir.rglob("*"):
                if item.is_file():
                    rel_path = item.relative_to(artifact_dir).as_posix()
                    s3_key = f"artifacts/{document_id}/{rel_path}"
                    self.s3_client.upload_file(
                        Filename=str(item),
                        Bucket=settings.R2_BUCKET_NAME,
                        Key=s3_key,
                    )
            logger.info(f"Synced artifacts for document {document_id} to Cloudflare R2")
        except Exception as e:
            logger.warning(f"Failed to sync artifacts to R2 for document {document_id}: {e}")

    async def delete_document_files(self, notebook_id: str, document_id: str, file_path: str) -> None:
        """Remove PDF and parser artifacts from both local disk and Cloudflare R2."""
        notebook_dir = (self.pdf_dir / notebook_id).resolve()
        stored_path = (settings.STORAGE_LOCAL_DIR / file_path).resolve()

        try:
            stored_path.relative_to(notebook_dir)
            is_document_pdf = stored_path.parent == notebook_dir and stored_path.name.startswith(f"{document_id}_")
        except ValueError:
            is_document_pdf = False

        # 1. Delete local PDF
        if is_document_pdf and stored_path.is_file():
            stored_path.unlink()
            logger.info(f"Deleted local PDF for document {document_id}: {stored_path}")

        # 2. Delete local artifacts
        artifact_dir = (self.artifacts_dir / document_id).resolve()
        try:
            artifact_dir.relative_to(self.artifacts_dir.resolve())
            if artifact_dir.is_dir():
                shutil.rmtree(artifact_dir)
                logger.info(f"Deleted local parser artifacts for document {document_id}: {artifact_dir}")
        except ValueError:
            logger.warning(f"Refused to delete artifacts outside storage for document {document_id}")

        # 3. Delete from Cloudflare R2
        if self.backend == "r2" and self.s3_client:
            try:
                # Delete PDF
                s3_pdf_key = f"pdfs/{notebook_id}/{stored_path.name}"
                self.s3_client.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=s3_pdf_key)
                logger.info(f"Deleted PDF from R2: {s3_pdf_key}")

                # Delete artifacts folder
                prefix = f"artifacts/{document_id}/"
                paginator = self.s3_client.get_paginator("list_objects_v2")
                for page in paginator.paginate(Bucket=settings.R2_BUCKET_NAME, Prefix=prefix):
                    if "Contents" in page:
                        delete_objects = [{"Key": obj["Key"]} for obj in page["Contents"]]
                        if delete_objects:
                            self.s3_client.delete_objects(
                                Bucket=settings.R2_BUCKET_NAME,
                                Delete={"Objects": delete_objects},
                            )
                logger.info(f"Cleaned artifacts from R2 for document {document_id}")
            except Exception as e:
                logger.warning(f"Error deleting files from Cloudflare R2 for document {document_id}: {e}")
