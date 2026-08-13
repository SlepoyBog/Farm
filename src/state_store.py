"""Reliable helpers for JSON state files used by the publishing pipeline."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class StateCorruptionError(RuntimeError):
    """Raised when critical persisted state is not valid JSON."""


def read_json(path: Path, default: Any, *, critical: bool = False) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        if critical:
            raise StateCorruptionError(f"Invalid JSON state in {path}: {exc}") from exc
        return default


def atomic_write_json(path: Path, data: Any) -> None:
    """Write JSON through a same-directory temporary file and atomic replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
