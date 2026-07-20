"""
build_backend.py — Build the PyInstaller backend bundle for PDF Extractor V3.

This script:
  1. Runs PyInstaller against backend.spec
  2. Copies the resulting dist/backend/ folder into electron/resources/backend/
  3. Copies config.json template into electron/resources/backend/ (if not already there)

Run from the PDF Extractor V3 directory:
    python build_backend.py
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

# Force UTF-8 on stdout/stderr so status glyphs never crash on Windows cp1252
# consoles (default code page). Without this, printing a checkmark raises
# UnicodeEncodeError and aborts build_all.bat before electron-builder runs.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT        = Path(__file__).parent.resolve()
SPEC_FILE   = ROOT / "backend.spec"
DIST_DIR    = ROOT / "dist" / "backend"
DEST_DIR    = ROOT / "electron" / "resources" / "backend"
CONFIG_TPL  = ROOT / "backend" / "config.json"


def run(cmd: list, **kwargs):
    print(f"\n  > {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(f"\n  ERROR: command exited with code {result.returncode}")
        sys.exit(result.returncode)


# Runtime imports the frozen backend MUST be able to satisfy. If any of these
# are missing from the *building* interpreter (sys.executable), PyInstaller will
# silently omit them and the shipped app fails at runtime (e.g. the Box JWT
# connection dies with ModuleNotFoundError: boxsdk). We refuse to build in that
# case so a broken bundle can never be produced again.
REQUIRED_RUNTIME_MODULES = ["boxsdk", "jwt", "fastapi", "uvicorn", "socketio", "fitz"]


def preflight_check():
    """Verify the interpreter running this build has every runtime dependency.

    The previous shipped build was produced with the WRONG interpreter (a venv
    that had SQLAlchemy/pandas but NOT boxsdk/fastapi), so boxsdk never made it
    into _internal/ and Box connections failed in the packaged app. Guard against
    a recurrence."""
    print(f"\n[0/3] Preflight: verifying build interpreter has runtime deps…")
    print(f"  Interpreter: {sys.executable}")
    missing = []
    for mod in REQUIRED_RUNTIME_MODULES:
        try:
            __import__(mod)
        except Exception as e:  # noqa: BLE001
            missing.append(f"{mod} ({e})")
    if missing:
        print("\n  ERROR: The interpreter used for this build is missing required")
        print("  runtime dependencies. PyInstaller would ship a BROKEN bundle.")
        for m in missing:
            print(f"    - {m}")
        print("\n  Fix: build with the interpreter that has the project deps, e.g.")
        print(f"    pip install -r requirements-build.txt")
        print(f"    python build_backend.py   (ensure `python` resolves to that env)")
        sys.exit(1)
    print(f"  OK — all {len(REQUIRED_RUNTIME_MODULES)} runtime modules importable.")


def main():
    print("=" * 60)
    print("  PDF Extractor V3 — Build Backend (PyInstaller)")
    print("=" * 60)

    preflight_check()

    # ── Step 1: Run PyInstaller ───────────────────────────────────────────────
    print("\n[1/3] Running PyInstaller…")

    run([sys.executable, "-m", "PyInstaller",
         "--distpath", str(ROOT / "dist"),
         "--workpath", str(ROOT / "build"),
         "--noconfirm",
         str(SPEC_FILE)],
        cwd=str(ROOT / "backend"))

    if not DIST_DIR.exists():
        print(f"\n  ERROR: Expected dist at {DIST_DIR} — PyInstaller may have failed.")
        sys.exit(1)

    print(f"  PyInstaller output: {DIST_DIR}")

    # ── Step 2: Copy to electron/resources/backend/ ───────────────────────────
    print(f"\n[2/3] Copying to {DEST_DIR} …")
    if DEST_DIR.exists():
        shutil.rmtree(DEST_DIR)
    shutil.copytree(str(DIST_DIR), str(DEST_DIR))
    print(f"  Copied {sum(1 for _ in DEST_DIR.rglob('*'))} files.")

    # ── Step 3: Copy config.json template ────────────────────────────────────
    dest_config = DEST_DIR / "config.json"
    if not dest_config.exists() and CONFIG_TPL.exists():
        shutil.copy2(str(CONFIG_TPL), str(dest_config))
        print(f"\n[3/3] Config template copied to {dest_config}")
    else:
        print(f"\n[3/3] config.json already exists at destination — skipped.")

    print("\n  ✅ Backend build complete.")
    print(f"  Output: {DEST_DIR}")
    print(f"  Entry:  {DEST_DIR / 'backend.exe'}\n")


if __name__ == "__main__":
    main()
