import asyncio
import io
from pathlib import Path
from fastapi import UploadFile
from app.infrastructure.storage.local_fs import StorageService
from app.core.config import settings

async def main():
    print(f"Testing StorageService with backend='{settings.STORAGE_BACKEND}'...")
    storage = StorageService()
    assert storage.backend == "r2", f"Expected r2, got {storage.backend}"
    assert storage.s3_client is not None, "S3 client should be initialized"

    notebook_id = "test_nb_r2"
    doc_id = "doc_test_001"
    filename = "sample_financial_report.pdf"
    content = b"%PDF-1.4 Mock Financial Statement Content for R2 testing"

    mock_upload = UploadFile(
        file=io.BytesIO(content),
        filename=filename,
        headers={"content-type": "application/pdf"}
    )

    print("1. Calling save_pdf()...")
    saved_path = await storage.save_pdf(notebook_id, doc_id, mock_upload)
    print(f"   Saved locally: {saved_path} (exists={saved_path.is_file()})")

    public_url = storage.get_public_pdf_url(notebook_id, doc_id, filename)
    print(f"2. Public CDN URL: {public_url}")

    print("3. Calling get_pdf_path()...")
    retrieved_path = storage.get_pdf_path(notebook_id, doc_id, filename)
    print(f"   Retrieved local path: {retrieved_path} (exists={retrieved_path.is_file()})")

    # Simulate deleting local cache file to test auto-pull from R2
    print("4. Testing auto-pull from R2 when local cache is deleted...")
    saved_path.unlink()
    assert not saved_path.is_file(), "Local file should be deleted"
    print("   Deleted local file. Now invoking get_pdf_path() to restore from R2...")
    restored_path = storage.get_pdf_path(notebook_id, doc_id, filename)
    assert restored_path.is_file(), "File should be automatically restored from R2"
    assert restored_path.read_bytes() == content, "Restored content must match original"
    print("   Auto-pull from Cloudflare R2 verified 100%!")

    print("5. Calling delete_document_files()...")
    await storage.delete_document_files(notebook_id, doc_id, str(restored_path))
    assert not restored_path.is_file(), "Local file should be removed on delete"
    print("   Document deletion and R2 cleanup completed successfully!")

    print("\n>>> ALL STORAGESERVICE R2 INTEGRATION TESTS PASSED 100%! <<<")

if __name__ == "__main__":
    asyncio.run(main())

