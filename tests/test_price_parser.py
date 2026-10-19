import pytest

from utils.price_parser import parse_listing_price, parse_price, parse_price_ceiling


@pytest.mark.unit
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("$12.99", 12.99),
        ("US $1,220.00", 1220.0),
        ("Price: $5", 5.0),
        ("no price here", None),
        (None, None),
    ],
)
def test_parse_price(text: str | None, expected: float | None) -> None:
    assert parse_price(text) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ILS 19.44", 19.44),
        ("ILS 1,261.91", 1261.91),
        ("₪50.00", 50.0),
        ("ILS 165.84ILS 331.68", 165.84),
    ],
)
def test_parse_price_local_currency(text: str, expected: float) -> None:
    assert parse_price(text) == expected


@pytest.mark.unit
def test_parse_price_ceiling_uses_range_max() -> None:
    assert parse_price_ceiling("$50.00 to $250.00") == 250.0
    assert parse_price_ceiling("US $19.99") == 19.99


@pytest.mark.unit
def test_parse_listing_price_prefers_current_then_range_max() -> None:
    assert parse_listing_price("ILS 165.84") == 165.84
    assert parse_listing_price("$50.00 to $250.00") == 250.0
