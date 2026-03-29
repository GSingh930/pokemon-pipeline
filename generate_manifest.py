"""
generate_manifest.py - Generates manifest.json files for your R2 bucket.
Run this after uploading footage and music to R2, then upload the manifests too.

Usage:
    python generate_manifest.py

This creates:
    footage/manifest.json   <- list of all clip filenames
    music/manifest.json     <- list of all music filenames

Then upload these manifest files to your R2 bucket in the same folders.
"""

import json
from pathlib import Path

def generate(folder: str, extensions: list):
    path = Path(folder)
    if not path.exists():
        print(f"Folder not found: {folder}")
        return

    files = []
    for ext in extensions:
        files.extend(p.name for p in sorted(path.glob(ext)))

    manifest_path = path / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(files, f, indent=2)

    print(f"Generated {manifest_path} with {len(files)} files:")
    for f in files:
        print(f"  {f}")

if __name__ == "__main__":
    generate("footage/library", ["*.mp4", "*.mov"])
    generate("music", ["*.mp3", "*.wav", "*.ogg", "*.m4a"])
    print("\nNow upload these manifest.json files to your R2 bucket.")
    print("  footage/library/manifest.json -> R2: footage/manifest.json")
    print("  music/manifest.json           -> R2: music/manifest.json")
