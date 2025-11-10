from __future__ import annotations

from typing import Iterable, Tuple


def pack_price_year_flags(price_toman: int, year: int, negotiable_flag: int) -> int:
    """Compact bit-packed representation in a single 64-bit int.

    Layout:
    - bits 0..1   : negotiable (0=nonnegotiable, 1=unknown, others reserved)
    - bits 2..33  : price (up to ~8e9 toman)
    - bits 34..49 : year (up to 2^16)
    - bits 50..63 : reserved
    """
    neg = (negotiable_flag & 0x3)
    p = max(price_toman, 0) & ((1 << 32) - 1)
    y = max(year, 0) & ((1 << 16) - 1)
    return (y << 34) | (p << 2) | neg


def unpack_price_year_flags(value: int) -> Tuple[int, int, int]:
    neg = value & 0x3
    p = (value >> 2) & ((1 << 32) - 1)
    y = (value >> 34) & ((1 << 16) - 1)
    return p, y, neg


def zero_copy_bytes_view(buf: bytearray) -> memoryview:
    """Return a zero-copy memoryview over a mutable bytearray buffer."""
    return memoryview(buf)


def bytes_from_ints(ints: Iterable[int]) -> bytearray:
    """Create a compact bytearray from small integers (0..255), suitable for memoryview usage."""
    return bytearray(int(i) & 0xFF for i in ints)

