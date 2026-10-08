"""Import patient bundles. Usage: python scripts/import_patients.py [dir]
`dir` is one bundle directory or a directory of them; defaults to data/patients.
Honors DATABASE_URL / SQLITE_PATH like the app. Rows with existing keys are skipped."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.importer import PATIENTS_DIR, import_all, import_bundle  # noqa: E402
from app.stores import get_store  # noqa: E402

if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else PATIENTS_DIR
    store = get_store()
    result = {target.name: import_bundle(store, target)} if (target / "patient.json").exists() else import_all(store, target)
    for pid, counts in result.items():
        print(f"{pid}: {sum(counts.values())} rows into {store.backend} ({len(counts)} tables)")
