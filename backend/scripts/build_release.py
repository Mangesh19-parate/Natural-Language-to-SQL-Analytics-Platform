#!/usr/bin/env python3
"""
Release Packaging Script (Repository Hygiene & Clean Distribution).
Generates a sanitized distribution archive (trustsql-release.zip) excluding local cache,
virtualenvs, local SQLite database states, test artifacts, and developer scratchpads.
"""

import os
import zipfile
import shutil

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUTPUT_DIR = os.path.join(ROOT_DIR, "dist")
OUTPUT_ZIP = os.path.join(OUTPUT_DIR, "trustsql-release.zip")

EXCLUDED_DIR_NAMES = {
    ".git",
    ".github",
    ".pytest_cache",
    ".hypothesis",
    ".reticle",
    "__pycache__",
    "node_modules",
    "local_data",
    "dist",
    ".vscode",
    ".idea",
    "coverage",
    ".system_generated",
    "scratch",
}

EXCLUDED_FILE_PATTERNS = {
    ".pyc",
    ".pyo",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".log",
    ".env",
    ".DS_Store",
}


def is_excluded(rel_path: str, filename: str) -> bool:
    parts = rel_path.replace("\\", "/").split("/")
    for part in parts:
        if part in EXCLUDED_DIR_NAMES:
            return True
    for ext in EXCLUDED_FILE_PATTERNS:
        if filename.endswith(ext):
            return True
    return False


def build_release():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if os.path.exists(OUTPUT_ZIP):
        os.remove(OUTPUT_ZIP)

    print(f"Packaging repository from: {ROOT_DIR}")
    packed_count = 0

    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(ROOT_DIR):
            rel_dir = os.path.relpath(root, ROOT_DIR)
            if rel_dir == ".":
                rel_dir = ""

            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIR_NAMES]

            for f in files:
                rel_file_path = os.path.join(rel_dir, f) if rel_dir else f
                if not is_excluded(rel_file_path, f):
                    abs_path = os.path.join(root, f)
                    zf.write(abs_path, arcname=rel_file_path)
                    packed_count += 1

    size_mb = os.path.getsize(OUTPUT_ZIP) / (1024 * 1024)
    print(f"Successfully created clean release archive: {OUTPUT_ZIP}")
    print(f"Total files packed: {packed_count} | Archive size: {size_mb:.2f} MB")


if __name__ == "__main__":
    build_release()
