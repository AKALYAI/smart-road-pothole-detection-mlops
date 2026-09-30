import os
import sys
import tempfile
from pathlib import Path

# make `import app...` work when running `pytest` from backend/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# isolated DB + uploads for the whole test session (must be set BEFORE app import)
_tmp = tempfile.mkdtemp(prefix="roadwatch-test-")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp}/test.db")
os.environ.setdefault("UPLOAD_DIR", f"{_tmp}/uploads")
os.environ.setdefault("REQUIRE_API_KEY", "false")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-pass")
os.environ.setdefault("MODEL_PATH", f"{_tmp}/no-model.pt")
os.environ.setdefault("DATASET_UPLOAD_DIR", f"{_tmp}/dataset-uploaded")
