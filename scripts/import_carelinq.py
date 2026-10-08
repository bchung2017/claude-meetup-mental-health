"""Import a CareLinq patient bundle directory. Usage: python scripts/import_carelinq.py [dir]
Defaults to data/sample. Honors DATABASE_URL / SQLITE_PATH like the app. Re-runs skip existing keys."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.carelinq import SAMPLE_DIR, import_bundle  # noqa: E402
from app.stores import get_store  # noqa: E402

if __name__ == "__main__":
    directory = Path(sys.argv[1]) if len(sys.argv) > 1 else SAMPLE_DIR
    store = get_store()
    counts = import_bundle(store, directory)
    print(f"imported into {store.backend}: " + ", ".join(f"{t}={n}" for t, n in counts.items()))
