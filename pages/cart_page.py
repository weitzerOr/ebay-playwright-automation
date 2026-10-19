from __future__ import annotations

import logging
import re

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from pages.base_page import BasePage
from utils.price_parser import parse_price

logger = logging.getLogger(__name__)


class CartPage(BasePage):
    # Header cart icon / link. Tried in order: count badge, cart host, path, hover id.
    CART_LINK = "#gh-cart-n, a[href*='cart.ebay.com'], a[href*='/cart'], a#gh-minicart-hover"
    # Order-summary amounts. Prefer item total, then subtotal, then older class names.
    SUBTOTAL_CANDIDATES = [
        "[data-test-id='ITEM_TOTAL']",
        "[data-test-id='SUBTOTAL']",
        "[data-test-id='cart-summary-subtotal']",
        ".val-col.total-row",
        "[class*='item-total']",
        "[class*='subtotal']",
    ]

    def __init__(self, page: Page) -> None:
        super().__init__(page)

    def open(self) -> None:
        """Open the cart from the header, or go directly to cart.ebay.com."""
        cart_link = self.page.locator(self.CART_LINK).first
        if self.visible(cart_link, timeout=2500):
            cart_link.click()
            self.page.wait_for_load_state("domcontentloaded")
        else:
            self.goto(self.settings.cart_url)
        self.dismiss_overlays()
        self.wait_for_network_idle()

    def read_item_subtotal(self) -> float:
        """Read the cart item total from structured locators, then labeled-row fallback."""
        for selector in self.SUBTOTAL_CANDIDATES:
            locator = self.page.locator(selector).first
            if self.visible(locator, timeout=1500):
                value = parse_price(locator.inner_text())
                if value is not None:
                    logger.info("Cart total from %s: %s", selector, value)
                    return value

        labeled = self._price_near_label(r"items?\s*\(\d+\)")
        if labeled is not None:
            logger.info("Cart item total from labeled row: %s", labeled)
            return labeled

        body = self.page.locator("body").inner_text()
        value = parse_price(body)
        if value is None:
            raise AssertionError("Could not read a cart total from the shopping cart page")
        logger.info("Cart total fallback from page text: %s", value)
        return value

    def _price_near_label(self, label_pattern: str) -> float | None:
        """Find a price in a summary row whose text matches label_pattern, skipping shipping/tax."""
        pattern = re.compile(label_pattern, re.I)
        rows = self.page.locator("div, tr, li, span, dt, dd")
        try:
            count = min(rows.count(), 250)
        except PlaywrightTimeoutError:
            return None
        for index in range(count):
            row = rows.nth(index)
            try:
                text = row.inner_text(timeout=300)
            except PlaywrightTimeoutError:
                continue
            if not text or not pattern.search(text):
                continue
            if "shipping" in text.lower() or "tax" in text.lower():
                continue
            value = parse_price(text)
            if value is not None:
                return value
        return None
