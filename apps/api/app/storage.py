from __future__ import annotations

import hashlib
import os
from pathlib import Path


class StorageAdapter:
    def put(self, key: str, content: bytes) -> str:
        raise NotImplementedError

    def get(self, key: str) -> bytes:
        raise NotImplementedError


class LocalStorage(StorageAdapter):
    def __init__(self, root: str | None = None) -> None:
        self.root = Path(
            root
            or os.getenv(
                "FIELDSIGHT_STORAGE_ROOT", Path(__file__).resolve().parents[1] / ".data" / "objects"
            )
        )
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, key: str, content: bytes) -> str:
        safe = key.replace("..", "_").lstrip("/")
        target = self.root / safe
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return safe

    def get(self, key: str) -> bytes:
        return (self.root / key).read_bytes()


class S3CompatibleStorage(StorageAdapter):
    """Production boundary; configure a real S3 client in deployment code."""

    def put(self, key: str, content: bytes) -> str:
        raise RuntimeError(
            "S3-compatible storage is an optional integration boundary and is not configured in demo mode."
        )

    def get(self, key: str) -> bytes:
        raise RuntimeError(
            "S3-compatible storage is an optional integration boundary and is not configured in demo mode."
        )


def checksum(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()
