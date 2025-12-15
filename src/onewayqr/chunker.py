from __future__ import annotations

import gzip
import hashlib
import io
import os
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

from .models import FileEntry, PreparedPayload, safe_relpath

READ_BUF = 1024 * 256


def _hashing_copy(src: io.BufferedReader, dst: io.BufferedWriter) -> Tuple[int, str]:
    """Copy stream while computing SHA256 over what is written."""
    hasher = hashlib.sha256()
    total = 0
    while True:
        chunk = src.read(READ_BUF)
        if not chunk:
            break
        dst.write(chunk)
        hasher.update(chunk)
        total += len(chunk)
    return total, hasher.hexdigest()


def _file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(READ_BUF), b""):
            h.update(chunk)
    return h.hexdigest()


def _gather_files(root: Path) -> List[FileEntry]:
    entries: List[FileEntry] = []
    if root.is_file():
        stat = root.stat()
        entries.append(
            FileEntry(
                path=root.name,
                size=stat.st_size,
                mtime=stat.st_mtime,
                mode=stat.st_mode,
            )
        )
        return entries
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            p = Path(dirpath) / name
            rel = safe_relpath(p, root)
            stat = p.stat()
            entries.append(
                FileEntry(
                    path=rel,
                    size=stat.st_size,
                    mtime=stat.st_mtime,
                    mode=stat.st_mode,
                )
            )
    return entries


def prepare_payload(
    input_path: str,
    compress: bool = False,
    root_name: Optional[str] = None,
) -> PreparedPayload:
    """
    Build a transferable payload and return metadata.
    - File -> raw copy (optionally gzipped)
    - Directory -> tar (optionally gzipped)
    - "-" -> stdin raw (optionally gzipped)
    """
    path_obj = Path(input_path) if input_path != "-" else None
    files: List[FileEntry] = []

    if input_path != "-" and path_obj.is_dir():
        packaging = "tar"
        compression = "gz" if compress else "none"
        suffix = ".tar.gz" if compress else ".tar"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp_path = tmp.name
        tmp.close()
        mode = "w:gz" if compress else "w:"
        base = root_name or path_obj.name
        with open(tmp_path, "wb") as fh:
            with tarfile.open(fileobj=fh, mode=mode) as tar:
                tar.add(str(path_obj), arcname=base)
        size = os.path.getsize(tmp_path)
        sha = _file_sha256(tmp_path)
        files = _gather_files(path_obj)
        return PreparedPayload(
            path=tmp_path,
            size=size,
            sha256=sha,
            compression=compression,
            packaging=packaging,
            root_name=base,
            files=files,
        )

    # File or stdin -> raw copy (optional gzip)
    packaging = "raw"
    compression = "gz" if compress else "none"
    suffix = ".gz" if compress else ".bin"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_path = tmp.name
    tmp.close()

    src_stream: io.BufferedReader
    if input_path == "-":
        src_stream = sys.stdin.buffer
        base = root_name or "stdin.bin"
    else:
        src_stream = open(path_obj, "rb")
        base = root_name or path_obj.name
        files = _gather_files(path_obj)

    if compress:
        with src_stream, gzip.open(tmp_path, "wb") as dst:
            size, _ = _hashing_copy(src_stream, dst)
        size = os.path.getsize(tmp_path)
        sha = _file_sha256(tmp_path)
    else:
        with src_stream, open(tmp_path, "wb") as dst:
            size, sha = _hashing_copy(src_stream, dst)

    return PreparedPayload(
        path=tmp_path,
        size=size,
        sha256=sha,
        compression=compression,
        packaging=packaging,
        root_name=base,
        files=files,
    )


def iter_chunks(path: str, chunk_size: int) -> Iterator[bytes]:
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk
