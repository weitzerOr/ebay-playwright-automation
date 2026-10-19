from __future__ import annotations

from typing import Any

import allure
import pytest

from services.ebay_shop_service import EbayShopService
from utils.data_loader import load_test_scenarios


def _scenario_id(scenario: dict[str, Any]) -> str:
    return str(scenario.get("id") or scenario.get("query") or "scenario")


@allure.epic("eBay")
@allure.feature("Search, cart, and budget assertion")
@pytest.mark.e2e
@pytest.mark.parametrize("scenario", load_test_scenarios(), ids=_scenario_id)
def test_search_add_to_cart_total_within_budget(
    ebay_shop: EbayShopService,
    scenario: dict[str, Any],
) -> None:
    query = scenario["query"]
    max_price = float(scenario["max_price"])
    limit = int(scenario.get("limit", 5))
    auth_mode = str(scenario.get("auth_mode", "guest"))

    allure.dynamic.parameter("query", query)
    allure.dynamic.parameter("max_price", max_price)
    allure.dynamic.parameter("limit", limit)
    allure.dynamic.parameter("auth_mode", auth_mode)

    ebay_shop.authenticate(auth_mode)
    urls = ebay_shop.search_items_by_name_under_price(query, max_price, limit)
    assert len(urls) <= limit
    assert urls, f"Expected at least one '{query}' listing priced at or below {max_price}"

    added = ebay_shop.add_items_to_cart(urls)
    ebay_shop.assert_cart_total_not_exceeds(max_price, len(added))
