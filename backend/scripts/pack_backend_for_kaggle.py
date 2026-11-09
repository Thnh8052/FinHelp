import os
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = BASE_DIR / "backend"
ZIP_OUTPUT = BASE_DIR / "backend_kaggle.zip"

EXCLUDE_DIRS = {".venv", "__pycache__", ".pytest_cache", "storage"}
EXCLUDE_EXTS = {".pyc", ".pyo"}

print(f"Creating {ZIP_OUTPUT.name} from {BACKEND_DIR}...")
with zipfile.ZipFile(ZIP_OUTPUT, "w", zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk(BACKEND_DIR):
        # Filter out unwanted directories
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        for file in files:
            file_path = Path(root) / file
            if file_path.suffix in EXCLUDE_EXTS:
                continue
            arcname = file_path.relative_to(BACKEND_DIR)
            zipf.write(file_path, arcname)

size_mb = ZIP_OUTPUT.stat().st_size / (1024 * 1024)
print(f"✅ Đã tạo thành công {ZIP_OUTPUT.name} (Dung lượng siêu nhẹ: {size_mb:.2f} MB)!")
