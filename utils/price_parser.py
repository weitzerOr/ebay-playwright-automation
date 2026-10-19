from __future__ import annotations

import re

_AMOUNT = r"([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?|[0-9]+(?:\.[0-9]{2})?)"
_PRICE_RE = re.compile(
    rf"(?:(?:US|USD|ILS|EUR|GBP|CAD|AUD)\s*)?(?:\$|€|£|₪)\s*{_AMOUNT}"
    rf"|(?:(?:US|USD|ILS|EUR|GBP|CAD|AUD)\s+){_AMOUNT}"
    rf"|{_AMOUNT}\s*(?:USD|ILS|EUR|GBP)",
    re.IGNORECASE,
)


def _amounts(text: str) -> list[float]:
    values: list[float] = []
    for match in _PRICE_RE.finditer(text.replace("\xa0", " ")):
        raw = next((group for group in match.groups() if group), None)
        if raw:
            values.append(float(raw.replace(",", "")))
    return values


def parse_price(text: str | None) -> float | None:
    """Return the first monetary value found in `text`, or None if absent."""
    if not text:
        return None
    values = _amounts(text)
    return values[0] if values else None


def parse_price_ceiling(text: str | None) -> float | None:
    """Return the highest price in a single value or a '$A to $B' range."""
    if not text:
        return None
    values = _amounts(text)
    return max(values) if values else None


def parse_listing_price(text: str | None) -> float | None:
    """Price used to decide whether a search card is within budget.

    Range listings (`$50 to $250`) use the ceiling so we do not pick an item
    that can exceed the budget. Single prices, including sale + original pairs
    in the same node, use the first (current) amount.
    """
    if not text:
        return None
    lowered = text.lower()
    if " to " in lowered or " – " in text or " - " in text:
        return parse_price_ceiling(text)
    return parse_price(text)
