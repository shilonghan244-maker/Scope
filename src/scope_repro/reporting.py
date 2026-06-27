from __future__ import annotations


def format_table_value(value: object) -> str:
    if isinstance(value, str):
        return value
    return f"{float(value):.12g}"
