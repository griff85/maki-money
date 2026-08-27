"""
Build script for MakiBot v2.
Run with: python build.py
Output:   dist/MakiBot/  (ready to zip and distribute)
"""

import os
import sys
import fnmatch
import shutil
import zipfile
import subprocess

ROOT     = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(ROOT, "dist", "MakiBot")

# accounts.json is written next to the exe at runtime, so any dist/ folder that
# has actually been run holds real credentials. The zip is committed to a public
# repo, so these must never survive into it.
SECRET_NAMES = {"accounts.json"}
SECRET_GLOBS = (".env*", "*.env", "*.pem", "*.key", "*_secret*", "*token*.json")


def is_secret(filename):
    return (filename in SECRET_NAMES
            or any(fnmatch.fnmatch(filename, g) for g in SECRET_GLOBS))


def run(cmd):
    print(f"\n> {' '.join(cmd)}\n")
    subprocess.run(cmd, check=True, cwd=ROOT)

# ── 1. Compile ────────────────────────────────────────────────────────────────
print("=== Compiling with PyInstaller ===")
run([sys.executable, "-m", "PyInstaller", "--clean", "-y", "MakiBot.spec"])

# ── 2. Copy runtime files ─────────────────────────────────────────────────────
print("\n=== Copying runtime files ===")

plugins_dst = os.path.join(DIST_DIR, "plugins")
if os.path.exists(plugins_dst):
    shutil.rmtree(plugins_dst)
shutil.copytree(os.path.join(ROOT, "plugins"), plugins_dst)
print(f"  Copied plugins/")

shutil.copy(os.path.join(ROOT, "manifest.json"), DIST_DIR)
print(f"  Copied manifest.json")

# ── 3. Strip credentials before packaging ─────────────────────────────────────
print("\n=== Scrubbing credentials from dist/ ===")
removed = []
for dirpath, _dirnames, filenames in os.walk(DIST_DIR):
    for fname in filenames:
        if is_secret(fname):
            path = os.path.join(dirpath, fname)
            os.remove(path)
            removed.append(os.path.relpath(path, DIST_DIR))
for r in removed:
    print(f"  Removed {r}")
if not removed:
    print("  Nothing to remove")

# ── 4. Zip it up ──────────────────────────────────────────────────────────────
print("\n=== Creating zip ===")
zip_path = os.path.join(ROOT, "dist", "MakiBot")
shutil.make_archive(zip_path, "zip", os.path.join(ROOT, "dist"), "MakiBot")
print(f"  Created dist/MakiBot.zip")

# ── 5. Verify nothing sensitive made it in ────────────────────────────────────
print("\n=== Verifying zip ===")
with zipfile.ZipFile(f"{zip_path}.zip") as z:
    entries = z.namelist()
leaked = [n for n in entries if is_secret(os.path.basename(n))]
if leaked:
    os.remove(f"{zip_path}.zip")
    print( "  *** ABORTED - credential files found in the zip: ***")
    for n in leaked:
        print(f"    {n}")
    print( "  The zip has been deleted so it cannot be distributed.")
    sys.exit(1)
print(f"  Clean - no credential files among {len(entries)} entries")

print(f"""
=== Build complete! ===

Folder:  {DIST_DIR}
Zip:     {zip_path}.zip

To distribute:
  Send dist/MakiBot.zip to your friend.
  They extract it and double-click MakiBot.exe.
  Chrome must be installed on their machine.
""")
