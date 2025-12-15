from __future__ import annotations

import argparse
import json
import os
import uuid
from typing import Iterable, Iterator, List, Sequence

import cv2

from . import config
from .chunker import iter_chunks, prepare_payload
from .fec import generate_parity_blocks
from .frames import Frame
from .models import FrameType, SessionMetadata, estimate_total_chunks, new_session_id
from .qrencode import compose_grid, make_qr_array, overlay_text


def _batched(seq: Iterable[Frame], n: int) -> Iterator[List[Frame]]:
    batch: List[Frame] = []
    for item in seq:
        batch.append(item)
        if len(batch) == n:
            yield batch
            batch = []
    if batch:
        yield batch


def build_metadata(
    payload_size: int,
    chunk_size: int,
    superblock_data: int,
    redundancy: int,
    sha256: str,
    packaging: str,
    compression: str,
    root_name: str,
    file_count: int,
    session_id: uuid.UUID | None = None,
) -> SessionMetadata:
    session = session_id or new_session_id()
    total_chunks = estimate_total_chunks(payload_size, chunk_size)
    return SessionMetadata(
        session_id=session,
        total_size=payload_size,
        chunk_size=chunk_size,
        total_chunks=total_chunks,
        superblock_data=superblock_data,
        redundancy=redundancy,
        sha256=sha256,
        packaging=packaging,
        compression=compression,
        root_name=root_name,
        file_count=file_count,
    )


def _header_frame(meta: SessionMetadata, flags: int = 0) -> Frame:
    payload = json.dumps(meta.to_dict(), separators=(",", ":")).encode()
    return Frame(
        frame_type=FrameType.SESSION_HEADER,
        session_id=meta.session_id.bytes,
        superblock_id=0,
        block_id=0,
        total_blocks=meta.total_chunks,
        blocks_in_super=0,
        flags=flags,
        payload=payload,
    )


def generate_frames(
    payload_path: str,
    meta: SessionMetadata,
    header_repeat: int = config.DEFAULT_HEADER_REPEAT,
    header_interval: int = config.DEFAULT_HEADER_INTERVAL,
) -> Iterator[Frame]:
    """Yield frames ready for encoding."""
    header = _header_frame(meta)
    for _ in range(max(1, header_repeat)):
        yield header

    block_id = 0
    superblock_id = 0
    chunk_iter = iter_chunks(payload_path, meta.chunk_size)

    while True:
        data_blocks: List[bytes] = []
        for _ in range(meta.superblock_data):
            try:
                block = next(chunk_iter)
            except StopIteration:
                break
            data_blocks.append(block)
        if not data_blocks:
            break

        blocks_in_super = len(data_blocks)
        # data frames
        for local_idx, block in enumerate(data_blocks):
            frame = Frame(
                frame_type=FrameType.DATA,
                session_id=meta.session_id.bytes,
                superblock_id=superblock_id,
                block_id=block_id,
                total_blocks=meta.total_chunks,
                blocks_in_super=blocks_in_super,
                flags=0,
                payload=block,
            )
            yield frame
            block_id += 1

        # parity frames
        parity_blocks = generate_parity_blocks(data_blocks, meta.redundancy)
        for parity_idx, parity in enumerate(parity_blocks):
            frame = Frame(
                frame_type=FrameType.FEC,
                session_id=meta.session_id.bytes,
                superblock_id=superblock_id,
                block_id=block_id + parity_idx,
                total_blocks=meta.total_chunks,
                blocks_in_super=blocks_in_super,
                flags=0,
                payload=parity,
            )
            yield frame

        superblock_id += 1

        # periodic header for resync
        if header_interval > 0 and (block_id % header_interval) == 0:
            yield header


def frames_to_qr_strings(frames: Sequence[Frame]) -> List[str]:
    return [f.to_b64() for f in frames]


def render_batches(
    frames: Iterable[Frame],
    rows: int,
    cols: int,
    fps: int,
    status_text: bool = True,
    output_video: str | None = None,
) -> None:
    grid_cells = rows * cols
    qr_arrays = []
    writer = None
    delay_ms = int(1000 / max(1, fps))

    for batch_idx, batch in enumerate(_batched(frames, grid_cells)):
        qr_strings = frames_to_qr_strings(batch)
        qr_arrays = [make_qr_array(s) for s in qr_strings]
        frame_img = compose_grid(qr_arrays, rows, cols)
        if status_text:
            info = f"batch {batch_idx} blocks~{batch[0].block_id if batch else 0}"
            frame_img = overlay_text(frame_img, info)

        display_img = frame_img
        # OpenCV VideoWriter expects color; convert if saving video
        if output_video:
            if writer is None:
                h, w = frame_img.shape
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(output_video, fourcc, fps, (w, h), isColor=False)
            writer.write(display_img)

        cv2.imshow("QR Sender", display_img)
        key = cv2.waitKey(delay_ms) & 0xFF
        if key in (ord("q"), 27):
            break

    if writer:
        writer.release()
    cv2.destroyAllWindows()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QR one-way sender")
    parser.add_argument("input", help="Path to file/dir or '-' for stdin")
    parser.add_argument("--chunk-size", type=int, default=config.DEFAULT_CHUNK_SIZE)
    parser.add_argument("--superblock-data", type=int, default=config.DEFAULT_SUPERBLOCK_DATA)
    parser.add_argument("--redundancy", type=int, default=config.DEFAULT_REDUNDANCY)
    parser.add_argument("--header-repeat", type=int, default=config.DEFAULT_HEADER_REPEAT)
    parser.add_argument("--header-interval", type=int, default=config.DEFAULT_HEADER_INTERVAL)
    parser.add_argument("--grid-rows", type=int, default=config.DEFAULT_GRID_ROWS)
    parser.add_argument("--grid-cols", type=int, default=config.DEFAULT_GRID_COLS)
    parser.add_argument("--fps", type=int, default=config.DEFAULT_FPS)
    parser.add_argument("--compress", action="store_true", help="Gzip payload before sending")
    parser.add_argument("--no-display", action="store_true", help="Do not open window")
    parser.add_argument("--video-output", help="Optional path to save MP4 of the QR stream")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.chunk_size <= 0:
        parser.error("chunk-size must be > 0")
    if args.superblock_data <= 0:
        parser.error("superblock-data must be > 0")
    if args.redundancy < 0:
        parser.error("redundancy must be >= 0")

    payload = prepare_payload(args.input, compress=args.compress)
    meta = build_metadata(
        payload_size=payload.size,
        chunk_size=args.chunk_size,
        superblock_data=args.superblock_data,
        redundancy=args.redundancy,
        sha256=payload.sha256,
        packaging=payload.packaging,
        compression=payload.compression,
        root_name=payload.root_name,
        file_count=len(payload.files),
    )
    frames = generate_frames(
        payload_path=payload.path,
        meta=meta,
        header_repeat=args.header_repeat,
        header_interval=args.header_interval,
    )

    print(
        f"[send] session={meta.session_id} bytes={payload.size} chunks={meta.total_chunks} "
        f"superblock_data={meta.superblock_data} redundancy={meta.redundancy} "
        f"grid={args.grid_rows}x{args.grid_cols} fps={args.fps}"
    )
    if args.video_output:
        print(f"[send] writing video to {args.video_output}")

    if args.no_display and not args.video_output:
        parser.error("When --no-display is set you must provide --video-output.")

    try:
        if args.no_display:
            # Render without opening a window
            grid_cells = args.grid_rows * args.grid_cols
            writer = None
            if args.video_output:
                sample_qr = make_qr_array("sample")
                h, w = sample_qr.shape
                frame_h = args.grid_rows * h + (args.grid_rows - 1) * config.DEFAULT_GAP
                frame_w = args.grid_cols * w + (args.grid_cols - 1) * config.DEFAULT_GAP
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(args.video_output, fourcc, args.fps, (frame_w, frame_h), isColor=False)

            for batch in _batched(frames, grid_cells):
                qr_arrays = [make_qr_array(s) for s in frames_to_qr_strings(batch)]
                frame_img = compose_grid(qr_arrays, args.grid_rows, args.grid_cols)
                if writer:
                    writer.write(frame_img)

            if writer:
                writer.release()
        else:
            render_batches(
                frames=frames,
                rows=args.grid_rows,
                cols=args.grid_cols,
                fps=args.fps,
                status_text=True,
                output_video=args.video_output,
            )
    finally:
        try:
            os.remove(payload.path)
        except OSError:
            pass


if __name__ == "__main__":
    main()
