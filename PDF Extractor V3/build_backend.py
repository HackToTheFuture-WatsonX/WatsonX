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
# NOTE: python-multipart imports as `multipart` in <=0.0.9 and as
# `python_multipart` in >=0.0.12. FastAPI accepts either. We accept either here
# too — the preflight below tries alternates and only fails if ALL variants are
# missing.
REQUIRED_RUNTIME_MODULES: list = [
    "boxsdk", "jwt", "fastapi", "uvicorn", "socketio", "fitz",
    # Needed by /api/scan/upload — without these the packaged app can save
    # zero bytes when a user picks a file, which is the exact "nothing happens"
    # symptom we've seen. Preflight refuses to build if they're missing.
    "aiofiles",
    ("multipart", "python_multipart"),  # tuple = accept any of these names
]


def preflight_check():
    """Verify the interpreter running this build has every runtime dependency.

    The previous shipped build was produced with the WRONG interpreter (a venv
    that had SQLAlchemy/pandas but NOT boxsdk/fastapi), so boxsdk never made it
    into _internal/ and Box connections failed in the packaged app. Guard against
    a recurrence — including for the newer multipart/aiofiles deps whose absence
    silently breaks the scan/upload endpoint."""
    print(f"\n[0/3] Preflight: verifying build interpreter has runtime deps…")
    print(f"  Interpreter: {sys.executable}")
    missing = []
    for entry in REQUIRED_RUNTIME_MODULES:
        # entry is either a str (single module) or a tuple (accept any of).
        candidates = (entry,) if isinstance(entry, str) else tuple(entry)
        last_err = None
        for name in candidates:
            try:
                __import__(name)
                last_err = None
                break
            except Exception as e:  # noqa: BLE001
                last_err = f"{name} ({e})"
        if last_err is not None:
            missing.append(" or ".join(candidates) + f" — last error: {last_err}")
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

    # boxsdk swallows crypto ImportErrors and sets JWTAuth = None. If that happens
    # in the *build* interpreter, the packaged app is guaranteed to fail Box JWT
    # auth with "'NoneType' object has no attribute 'from_settings_dictionary'".
    # Verify JWTAuth is a real class BEFORE building so we never ship it broken.
    try:
        from boxsdk import JWTAuth as _JWTAuth
    except Exception as e:  # noqa: BLE001
        print(f"\n  ERROR: could not import boxsdk.JWTAuth: {e}")
        sys.exit(1)
    if _JWTAuth is None:
        print("\n  ERROR: boxsdk.JWTAuth is None in the build interpreter.")
        print("  This means boxsdk's crypto extras (cryptography + PyJWT) failed to")
        print("  import. The packaged app WILL fail Box JWT auth. Fix with:")
        print("    pip install 'boxsdk[jwt]' cryptography PyJWT")
        sys.exit(1)
    print("  OK — boxsdk.JWTAuth is a real class (crypto extras present).")



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
