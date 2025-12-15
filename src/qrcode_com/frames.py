from __future__ import annotations

import base64
import struct
import zlib
from dataclasses import dataclass

from . import config
from .models import FrameType

_HEADER_STRUCT = struct.Struct(">4sBBB16sIIIHH")
_CRC_STRUCT = struct.Struct(">I")


class FrameError(Exception):
    pass


@dataclass
class Frame:
    frame_type: FrameType
    session_id: bytes  # 16 bytes (uuid)
    superblock_id: int
    block_id: int
    total_blocks: int
    blocks_in_super: int
    flags: int
    payload: bytes

    def to_bytes(self) -> bytes:
        if len(self.session_id) != 16:
            raise FrameError("session_id must be 16 bytes")
        payload_len = len(self.payload)
        if payload_len > 0xFFFF:
            raise FrameError("payload too large for frame")
        header = _HEADER_STRUCT.pack(
            config.MAGIC,
            config.VERSION,
            int(self.frame_type),
            self.flags & 0xFF,
            self.session_id,
            int(self.superblock_id),
            int(self.block_id),
            int(self.total_blocks),
            int(self.blocks_in_super),
            payload_len,
        )
        crc = zlib.crc32(header + self.payload) & 0xFFFFFFFF
        return header + self.payload + _CRC_STRUCT.pack(crc)

    @classmethod
    def from_bytes(cls, data: bytes) -> "Frame":
        if len(data) < _HEADER_STRUCT.size + _CRC_STRUCT.size:
            raise FrameError("frame too short")
        header = data[: _HEADER_STRUCT.size]
        (
            magic,
            version,
            frame_type,
            flags,
            session_id,
            superblock_id,
            block_id,
            total_blocks,
            blocks_in_super,
            payload_len,
        ) = _HEADER_STRUCT.unpack(header)
        if magic != config.MAGIC:
            raise FrameError("bad magic")
        if version != config.VERSION:
            raise FrameError(f"unsupported version {version}")
        expected_len = _HEADER_STRUCT.size + payload_len + _CRC_STRUCT.size
        if len(data) != expected_len:
            raise FrameError("frame length mismatch")
        payload = data[_HEADER_STRUCT.size : _HEADER_STRUCT.size + payload_len]
        crc_stored = _CRC_STRUCT.unpack(data[-_CRC_STRUCT.size :])[0]
        crc_calc = zlib.crc32(header + payload) & 0xFFFFFFFF
        if crc_calc != crc_stored:
            raise FrameError("CRC mismatch")
        return cls(
            frame_type=FrameType(frame_type),
            session_id=session_id,
            superblock_id=superblock_id,
            block_id=block_id,
            total_blocks=total_blocks,
            blocks_in_super=blocks_in_super,
            flags=flags,
            payload=payload,
        )

    def to_b64(self) -> str:
        return base64.b64encode(self.to_bytes()).decode("ascii")

    @classmethod
    def from_b64(cls, data: str) -> "Frame":
        try:
            raw = base64.b64decode(data, validate=True)
        except Exception as exc:  # noqa: BLE001
            raise FrameError(f"base64 decode failed: {exc}") from exc
        return cls.from_bytes(raw)
