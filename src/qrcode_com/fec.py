from __future__ import annotations

from typing import List


def xor_parity_block(blocks: List[bytes]) -> bytes:
    """Return a single XOR parity block across all provided blocks."""
    if not blocks:
        return b""
    max_len = max(len(b) for b in blocks)
    parity = bytearray(max_len)
    for block in blocks:
        padded = block.ljust(max_len, b"\0")
        for i, val in enumerate(padded):
            parity[i] ^= val
    return bytes(parity)


def generate_parity_blocks(blocks: List[bytes], count: int) -> List[bytes]:
    """Generate `count` identical parity blocks (simple XOR)."""
    if count <= 0:
        return []
    parity = xor_parity_block(blocks)
    return [parity for _ in range(count)]


def recover_single_missing(
    known_blocks: List[bytes],
    parity_block: bytes,
    missing_count: int,
) -> bytes | None:
    """
    Recover a single missing block using XOR parity.
    Returns the recovered block bytes or None if not possible.
    """
    if missing_count != 1 or not parity_block:
        return None
    blocks = list(known_blocks)
    blocks.append(parity_block)
    return xor_parity_block(blocks)
