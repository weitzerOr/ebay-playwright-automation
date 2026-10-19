from __future__ import annotations

import re

_ITEM_ID_RE = re.compile(r"/itm/(?:[^/]+/)?(\d{9,})")


def item_id_from_url(url: str) -> str | None:
    match = _ITEM_ID_RE.search(url)
    return match.group(1) if match else None


def canonical_item_url(url: str) -> str | None:
    item_id = item_id_from_url(url)
    if not item_id:
        return None
    return f"https://www.ebay.com/itm/{item_id}"
