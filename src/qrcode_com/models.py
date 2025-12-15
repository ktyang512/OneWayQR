from __future__ import annotations

import dataclasses
import enum
import os
import uuid
from typing import List, Optional


class FrameType(enum.IntEnum):
    SESSION_HEADER = 0
    DATA = 1
    FEC = 2
    INDEX = 3


@dataclasses.dataclass
class FileEntry:
    path: str
    size: int
    mtime: float
    mode: Optional[int] = None


@dataclasses.dataclass
class PreparedPayload:
    path: str
    size: int
    sha256: str
    compression: str  # "none" or "gz"
    packaging: str  # e.g., "tar"
    root_name: str
    files: List[FileEntry]


@dataclasses.dataclass
class SessionMetadata:
    session_id: uuid.UUID
    total_size: int
    chunk_size: int
    total_chunks: int
    superblock_data: int
    redundancy: int
    sha256: str
    packaging: str
    compression: str
    root_name: str
    file_count: int

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id.hex,
            "total_size": self.total_size,
            "chunk_size": self.chunk_size,
            "total_chunks": self.total_chunks,
            "superblock_data": self.superblock_data,
            "redundancy": self.redundancy,
            "sha256": self.sha256,
            "packaging": self.packaging,
            "compression": self.compression,
            "root_name": self.root_name,
            "file_count": self.file_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionMetadata":
        return cls(
            session_id=uuid.UUID(hex=data["session_id"]),
            total_size=int(data["total_size"]),
            chunk_size=int(data["chunk_size"]),
            total_chunks=int(data["total_chunks"]),
            superblock_data=int(data["superblock_data"]),
            redundancy=int(data["redundancy"]),
            sha256=data["sha256"],
            packaging=data["packaging"],
            compression=data["compression"],
            root_name=data.get("root_name", ""),
            file_count=int(data.get("file_count", 0)),
        )


def estimate_total_chunks(total_size: int, chunk_size: int) -> int:
    return (total_size + chunk_size - 1) // chunk_size


def new_session_id() -> uuid.UUID:
    return uuid.uuid4()


def safe_relpath(path: str, root: str) -> str:
    try:
        rel = os.path.relpath(path, root)
    except ValueError:
        rel = os.path.basename(path)
    if rel == ".":
        return os.path.basename(path)
    return rel
