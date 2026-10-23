"""Atomic course state; no private data in a Git checkout."""

import json
import os
import tempfile
from pathlib import Path


def private_root(path):
    root = Path(path).resolve()
    if any((p / ".git").exists() for p in (root, *root.parents)):
        raise ValueError("Private student data must be outside every Git checkout")
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".checkpoint-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def load_state(root):
    state = json.loads((Path(root) / "state.json").read_text(encoding="utf-8"))
    version = state.get("schema_version")
    if version != 1:
        raise ValueError(f"Unsupported state version {version}; explicit migration required, original preserved")
    return state
