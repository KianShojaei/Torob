#!/usr/bin/env python3
"""Unpack the challenge bundle into ./data, then build + validate the serving DB.

    python scripts/prepare_dataset.py data/starcoach-dataset-v16.zip
    python scripts/prepare_dataset.py            # uses whatever is already in ./data
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PY = sys.executable
NEEDED = ("shops.csv", "products.csv", "offers.csv")


def unpack(bundle: Path) -> None:
    with zipfile.ZipFile(bundle) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not names:
            raise SystemExit("the archive contains no CSV files")
        for name in names:
            target = DATA / Path(name).name
            with zf.open(name) as src, open(target, "wb") as dst:
                dst.write(src.read())
            print(f"  extracted {target.name}  ({target.stat().st_size / 1e6:.1f} MB)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle", nargs="?", help="zip file to unpack into ./data")
    ap.add_argument("--db", default="backend/var/app.db")
    args = ap.parse_args()

    DATA.mkdir(exist_ok=True)
    if args.bundle:
        path = Path(args.bundle)
        if not path.exists():
            raise SystemExit(f"not found: {path}")
        print(f"▶ unpacking {path.name}")
        unpack(path)

    missing = [n for n in NEEDED if not (DATA / n).exists()]
    if missing:
        raise SystemExit(
            "missing CSVs in ./data: " + ", ".join(missing)
            + "\n  drop them there or pass the .zip bundle as an argument"
        )

    # a real dataset must not be labelled synthetic
    truth = DATA / "synthetic_truth.json"
    if truth.exists():
        truth.unlink()
        print("  removed synthetic_truth.json (real dataset)")

    db = str(ROOT / args.db)
    print("▶ building the serving database")
    subprocess.run([PY, "-m", "app.etl.build", "--data", str(DATA), "--db", db],
                   cwd=ROOT / "backend", check=True)

    print("▶ validating")
    proc = subprocess.run([PY, "-m", "app.etl.validate", "--db", db],
                          cwd=ROOT / "backend", check=False)
    report = ROOT / "backend" / "var" / "etl-validation.json"
    if report.exists():
        data = json.loads(report.read_text())
        print(json.dumps(data.get("metrics", {}), indent=2, ensure_ascii=False))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
