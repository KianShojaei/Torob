import gzip
import shutil
from pathlib import Path
from backend.app.config import settings

def ensure_db_ready():
    """
    On a fresh server or Docker container cloned from GitHub, if `data/torob_assistant.db`
    is not present, automatically unpack `data/torob_portable.db.gz` in ~2 seconds!
    """
    db_path = settings.SQLITE_DB_PATH
    if db_path.exists() and db_path.stat().st_size > 100_000:
        return

    gz_path = Path("data/torob_portable.db.gz")
    if gz_path.exists():
        print("🚀 Unpacking portable database bundle for server startup...")
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(gz_path, "rb") as f_in:
            with open(db_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        print(f"✅ Database ready at {db_path}")
