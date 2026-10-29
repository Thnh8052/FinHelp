import shutil
from pathlib import Path
from fastapi import UploadFile
from app.core.config import settings
from app.core.logging import logger


class StorageService:
    """Manages file persistence for uploaded PDFs and parsing artifacts.

    Defaults to local filesystem for development; can be swapped with S3 / MinIO for production.
    """

    def __init__(self):
        self.pdf_dir = settings.PDF_STORAGE_DIR
        self.artifacts_dir = settings.ARTIFACTS_STORAGE_DIR
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    async def save_pdf(self, notebook_id: str, document_id: str, file: UploadFile) -> Path:
        dest_folder = self.pdf_dir / notebook_id
        dest_folder.mkdir(parents=True, exist_ok=True)
        dest_path = dest_folder / f"{document_id}_{Path(file.filename).name}"  # .name: no path traversal via the filename

        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        logger.info(f"Saved PDF to: {dest_path}")
        return dest_path

    def get_pdf_path(self, notebook_id: str, document_id: str, filename: str) -> Path:
        return self.pdf_dir / notebook_id / f"{document_id}_{Path(filename).name}"

    async def delete_document_files(self, notebook_id: str, document_id: str, file_path: str) -> None:
        """Remove only the PDF and parser artifacts owned by one document.

        ``file_path`` comes from MongoDB, so it is validated against the notebook's
        PDF directory before deletion instead of being treated as a trusted path.
        """
        notebook_dir = (self.pdf_dir / notebook_id).resolve()
        stored_path = Path(file_path).resolve()

        try:
            stored_path.relative_to(notebook_dir)
            is_document_pdf = stored_path.parent == notebook_dir and stored_path.name.startswith(f"{document_id}_")
        except ValueError:
            is_document_pdf = False

        if is_document_pdf and stored_path.is_file():
            stored_path.unlink()
            logger.info(f"Deleted PDF for document {document_id}: {stored_path}")

        artifact_dir = (self.artifacts_dir / document_id).resolve()
        try:
            artifact_dir.relative_to(self.artifacts_dir.resolve())
        except ValueError:
            logger.warning(f"Refused to delete artifacts outside storage for document {document_id}")
            return

        if artifact_dir.is_dir():
            shutil.rmtree(artifact_dir)
            logger.info(f"Deleted parser artifacts for document {document_id}: {artifact_dir}")
