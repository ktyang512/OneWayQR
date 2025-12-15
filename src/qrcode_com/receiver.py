from __future__ import annotations

import argparse
import gzip
import json
import os
import shutil
import sys
import tarfile
import time
from pathlib import Path
from typing import Dict, List, Optional

import cv2

from . import config
from .fec import recover_single_missing
from .frames import Frame, FrameError
from .models import FrameType, SessionMetadata


def _file_sha256(path: str) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 256), b""):
            h.update(chunk)
    return h.hexdigest()


class Reassembler:
    def __init__(self) -> None:
        self.meta: Optional[SessionMetadata] = None
        self.session_id: Optional[bytes] = None
        self.data_blocks: Dict[int, bytes] = {}
        self.parity_blocks: Dict[int, List[bytes]] = {}
        self.headers_seen = 0

    def ingest(self, frame: Frame) -> None:
        if frame.frame_type == FrameType.SESSION_HEADER:
            self._handle_header(frame)
            return
        if self.session_id and frame.session_id != self.session_id:
            return  # different session
        if not self.meta:
            return  # ignore until header

        if frame.frame_type == FrameType.DATA:
            if frame.block_id not in self.data_blocks:
                self.data_blocks[frame.block_id] = frame.payload
                self._maybe_recover(frame.superblock_id)
        elif frame.frame_type == FrameType.FEC:
            self.parity_blocks.setdefault(frame.superblock_id, []).append(frame.payload)
            self._maybe_recover(frame.superblock_id)

    def _handle_header(self, frame: Frame) -> None:
        try:
            meta = SessionMetadata.from_dict(json.loads(frame.payload.decode()))
        except Exception:
            return
        if self.session_id and frame.session_id != self.session_id:
            return
        self.session_id = frame.session_id
        self.meta = meta
        self.headers_seen += 1

    def _expected_len(self, block_id: int) -> int:
        assert self.meta is not None
        if block_id < self.meta.total_chunks - 1:
            return self.meta.chunk_size
        return self.meta.total_size - self.meta.chunk_size * (self.meta.total_chunks - 1)

    def _maybe_recover(self, superblock_id: int) -> None:
        if not self.meta:
            return
        start = superblock_id * self.meta.superblock_data
        end = min(start + self.meta.superblock_data, self.meta.total_chunks)
        indices = list(range(start, end))
        missing = [i for i in indices if i not in self.data_blocks]
        if not missing:
            return
        parity = self.parity_blocks.get(superblock_id)
        if not parity:
            return
        recovered = recover_single_missing(
            [self.data_blocks[i] for i in indices if i in self.data_blocks],
            parity[0],
            len(missing),
        )
        if recovered is None:
            return
        block_id = missing[0]
        expected_len = self._expected_len(block_id)
        self.data_blocks[block_id] = recovered[:expected_len]

    def is_complete(self) -> bool:
        return bool(self.meta) and len(self.data_blocks) >= (self.meta.total_chunks if self.meta else 0)

    def write_payload(self, path: str) -> None:
        if not self.meta:
            raise RuntimeError("No session metadata available")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            for idx in range(self.meta.total_chunks):
                if idx not in self.data_blocks:
                    raise RuntimeError(f"Missing block {idx}")
                f.write(self.data_blocks[idx])

    def progress(self) -> str:
        if not self.meta:
            return "waiting for header"
        return f"{len(self.data_blocks)}/{self.meta.total_chunks} blocks ({len(self.data_blocks)/self.meta.total_chunks*100:.1f}%)"


def extract_payload(meta: SessionMetadata, payload_path: str, output: str, extract: bool) -> str:
    """Return final output path."""
    output_path = Path(output)
    if meta.packaging == "tar" and extract:
        output_path.mkdir(parents=True, exist_ok=True)
        with tarfile.open(payload_path, "r:*") as tar:
            tar.extractall(output_path)
        return str(output_path)

    if meta.packaging == "raw":
        if meta.compression == "gz":
            dest = output_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(payload_path, "rb") as src, open(dest, "wb") as dst:
                shutil.copyfileobj(src, dst)
            return str(dest)
        else:
            dest = output_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(payload_path, dest)
            return str(dest)

    # default: just copy payload
    dest = output_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(payload_path, dest)
    return str(dest)


def process_stream(
    source: str,
    grid_rows: int,
    grid_cols: int,
    camera: bool = False,
    output_path: str = "received.bin",
    extract: bool = False,
) -> None:
    cap = cv2.VideoCapture(0 if camera else source)
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open {'camera' if camera else source}")
    detector = cv2.QRCodeDetector()
    assembler = Reassembler()
    last_report = time.time()
    payload_tmp = "payload.tmp"

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            retval, decoded_info, points, _ = detector.detectAndDecodeMulti(gray)
            if retval:
                for data in decoded_info:
                    if not data:
                        continue
                    try:
                        frame_obj = Frame.from_b64(data)
                    except FrameError:
                        continue
                    assembler.ingest(frame_obj)
            now = time.time()
            if now - last_report > 1.0:
                print(f"[receive] {assembler.progress()}")
                last_report = now
            if assembler.is_complete():
                break
        cap.release()
    finally:
        cap.release()

    if not assembler.meta:
        raise RuntimeError("No session header received; cannot assemble payload.")
    try:
        assembler.write_payload(payload_tmp)
        sha = _file_sha256(payload_tmp)
        if sha != assembler.meta.sha256:
            raise RuntimeError(f"SHA256 mismatch; expected {assembler.meta.sha256}, got {sha}")
        final_path = extract_payload(assembler.meta, payload_tmp, output_path, extract=extract)
        print(f"[receive] payload restored to {final_path}")
    finally:
        if os.path.exists(payload_tmp):
            os.remove(payload_tmp)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QR one-way receiver")
    parser.add_argument("--input", help="Video file path; omit to use camera", default=None)
    parser.add_argument("--grid-rows", type=int, default=config.DEFAULT_GRID_ROWS)
    parser.add_argument("--grid-cols", type=int, default=config.DEFAULT_GRID_COLS)
    parser.add_argument("--output", default="received.bin", help="Output file/dir")
    parser.add_argument("--extract", action="store_true", help="Extract tar payloads or decompress gz payloads")
    return parser


def main(argv: List[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    camera = args.input is None
    process_stream(
        source=args.input or "0",
        grid_rows=args.grid_rows,
        grid_cols=args.grid_cols,
        camera=camera,
        output_path=args.output,
        extract=args.extract,
    )


if __name__ == "__main__":
    main()
