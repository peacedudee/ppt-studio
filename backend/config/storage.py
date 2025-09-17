"""Helpers for obtaining a storage client across environments."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Iterable, Iterator

from google.cloud import storage


class LocalBlob:
    def __init__(self, root: Path, name: str) -> None:
        self._root = root
        self.name = name
        self._path = self._root / name
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def upload_from_file(self, file_obj, content_type: str | None = None) -> None:
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)
        with open(self._path, "wb") as fh:
            shutil.copyfileobj(file_obj, fh)
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)

    def upload_from_filename(self, filename: str) -> None:
        shutil.copyfile(filename, self._path)

    def upload_from_string(self, data: str, content_type: str | None = None) -> None:
        with open(self._path, "w", encoding="utf-8") as fh:
            fh.write(data)

    def download_to_filename(self, filename: str) -> None:
        shutil.copyfile(self._path, filename)

    def download_as_text(self) -> str:
        with open(self._path, "r", encoding="utf-8") as fh:
            return fh.read()

    def delete(self) -> None:
        if self._path.exists():
            self._path.unlink()

    def exists(self) -> bool:
        return self._path.exists()

    def open(self, mode: str = "rb"):
        return open(self._path, mode)

    def generate_signed_url(self, **_: object) -> str:
        return f"file://{self._path}"


class LocalBucket:
    def __init__(self, base: Path, name: str) -> None:
        self.name = name
        self._root = base / name
        self._root.mkdir(parents=True, exist_ok=True)

    def blob(self, name: str) -> LocalBlob:
        return LocalBlob(self._root, name)

    def list_blobs(self, prefix: str | None = None) -> Iterator[LocalBlob]:
        prefix = prefix or ""
        for path in self._root.rglob("*"):
            if path.is_file():
                rel = path.relative_to(self._root).as_posix()
                if rel.startswith(prefix):
                    yield LocalBlob(self._root, rel)

    def exists(self) -> bool:
        return self._root.exists()


class LocalStorageClient:
    """File system backed storage client for local development/testing."""

    def __init__(self, base_path: str | None = None) -> None:
        root = base_path or os.getenv("LOCAL_STORAGE_PATH", "/tmp/ppt-studio-storage")
        self._base = Path(root)
        self._base.mkdir(parents=True, exist_ok=True)

    def bucket(self, name: str) -> LocalBucket:
        return LocalBucket(self._base, name)

    def list_buckets(self) -> Iterable[LocalBucket]:
        for child in self._base.iterdir():
            if child.is_dir():
                yield LocalBucket(self._base, child.name)
