from __future__ import annotations


def cooperative_message_count(coalition_size: int) -> int:
    return 4 * coalition_size - 1


def cooperative_payload_bytes(coalition_size: int, union_requests: int) -> int:
    return 160 * coalition_size - 56 + 64 * union_requests
