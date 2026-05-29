from __future__ import annotations

from slugify import slugify as _slugify


def slugify(text: str) -> str:
    return _slugify(text, separator="-", lowercase=True)
