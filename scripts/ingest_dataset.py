#!/usr/bin/env python3
"""One command to go from the challenge bundle to a serving database.

    python scripts/ingest_dataset.py data/starcoach-dataset.zip
    python scripts/ingest_dataset.py data/            # folder with the three CSVs

Steps: unpack → profile → build → validate, then print the numbers that matter
(and the ones the UI will display). Safe to re-run.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
PY = sys.executable
NEEDED = ("shops.csv", "products.csv", "offers.csv")


def log(msg: str) -> None:
    print(f"\033[36m▸\033[0m {msg}")


def unpack(source: Path, data_dir: Path) -> None:
    if source.is_dir():
        return
    if source.suffix.lower() != ".zip":
        raise SystemExit(f"expected a .zip or a folder, got {source}")
    log(f"unpacking {source.name}")
    with zipfile.ZipFile(source) as zf:
        for member in zf.namelist():
            if member.lower().endswith(".csv"):
                target = data_dir / Path(member).name
                with zf.open(member) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst, length=1 << 20)
                print(f"    {member} → {target.name}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", nargs="?", default="data",
                    help="zip bundle or folder containing shops/products/offers CSV")
    ap.add_argument("--data", default="data", help="destination folder for the CSVs")
    ap.add_argument("--db", default="backend/var/app.db", help="serving database path")
    ap.add_argument("--skip-profile", action="store_true")
    ap.add_argument("--keep-synthetic", action="store_true",
                    help="keep synthetic_truth.json (forces dataset_mode=synthetic)")
    args = ap.parse_args()

    data_dir = (ROOT / args.data).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    source = (ROOT / args.source).resolve() if not Path(args.source).is_absolute() else Path(args.source)

    if not source.exists():
        raise SystemExit(f"not found: {source}")

    unpack(source, data_dir)

    missing = [n for n in NEEDED if not (data_dir / n).exists()]
    if missing:
        raise SystemExit(
            "missing CSVs: " + ", ".join(missing)
            + f"\n  put them in {data_dir} or pass the .zip bundle"
        )

    # a stale truth file would make the app label real data as synthetic
    truth = data_dir / "synthetic_truth.json"
    if truth.exists() and not args.keep_synthetic:
        log("removing synthetic_truth.json (real dataset)")
        truth.unlink()

    sizes = {n: round((data_dir / n).stat().st_size / 1e6, 1) for n in NEEDED}
    log(f"inputs: {sizes}")

    if not args.skip_profile:
        log("profiling")
        subprocess.run(
            [PY, "tools/profile_dataset.py", str(data_dir), "--out", "reports"],
            cwd=ROOT, check=False,
        )

    log("building serving database")
    subprocess.run(
        [PY, "-m", "app.etl.build", "--data", str(data_dir), "--db", str((ROOT / args.db).resolve())],
        cwd=BACKEND, check=True,
    )

    log("validating")
    subprocess.run(
        [PY, "-m", "app.etl.validate", "--db", str((ROOT / args.db).resolve())],
        cwd=BACKEND, check=True,
    )

    meta = subprocess.run(
        [PY, "-c", "from app.api.routes import meta; import json; print(json.dumps(meta(), ensure_ascii=False))"],
        cwd=BACKEND, capture_output=True, text=True, check=False,
    )
    if meta.returncode == 0:
        try:
            m = json.loads(meta.stdout)
            print("\nmode:", m.get("dataset_mode"), "| counts:", m.get("counts"))
        except json.JSONDecodeError:
            pass

    print("\nnext:  make build && make serve   (or: docker compose up --build)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
