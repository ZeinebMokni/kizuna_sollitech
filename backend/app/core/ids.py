"""UUIDv7 generator (time-ordered UUIDs give better B-tree index locality).

Python < 3.14 has no uuid.uuid7, so we implement RFC 9562 directly.
"""

import os
import time
import uuid


def uuid7() -> uuid.UUID:
    ts_ms = time.time_ns() // 1_000_000
    rand = int.from_bytes(os.urandom(10), "big")
    value = (ts_ms & ((1 << 48) - 1)) << 80
    value |= 0x7 << 76  # version
    value |= ((rand >> 68) & 0x0FFF) << 64  # 12 bits rand_a
    value |= 0b10 << 62  # variant
    value |= rand & ((1 << 62) - 1)  # 62 bits rand_b
    return uuid.UUID(int=value)
