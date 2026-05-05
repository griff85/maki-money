"""
Build script for MakiBot v2.
Run with: python build.py
Output:   dist/MakiBot/  (ready to zip and distribute)
"""

import os
import sys
import shutil
import subprocess

ROOT     = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(ROOT, "dist", "MakiBot")

def run(cmd):
    print(f"\n> {' '.join(cmd)}\n")
    subprocess.run(cmd, check=True, cwd=ROOT)

# ── 1. Compile ────────────────────────────────────────────────────────────────
print("=== Compiling with PyInstaller ===")
run([sys.executable, "-m", "PyInstaller", "--clean", "MakiBot.spec"])

# ── 2. Copy runtime files ─────────────────────────────────────────────────────
print("\n=== Copying runtime files ===")

plugins_dst = os.path.join(DIST_DIR, "plugins")
if os.path.exists(plugins_dst):
    shutil.rmtree(plugins_dst)
shutil.copytree(os.path.join(ROOT, "plugins"), plugins_dst)
print(f"  Copied plugins/")

shutil.copy(os.path.join(ROOT, "manifest.json"), DIST_DIR)
print(f"  Copied manifest.json")

# ── 3. Zip it up ──────────────────────────────────────────────────────────────
print("\n=== Creating zip ===")
zip_path = os.path.join(ROOT, "dist", "MakiBot")
shutil.make_archive(zip_path, "zip", os.path.join(ROOT, "dist"), "MakiBot")
print(f"  Created dist/MakiBot.zip")

print(f"""
=== Build complete! ===

Folder:  {DIST_DIR}
Zip:     {zip_path}.zip

To distribute:
  Send dist/MakiBot.zip to your friend.
  They extract it and double-click MakiBot.exe.
  Chrome must be installed on their machine.
""")
