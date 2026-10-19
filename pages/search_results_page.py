from __future__ import annotations

import logging
from dataclasses import dataclass

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from pages.base_page import BasePage
from utils.price_parser import parse_listing_price
from utils.url_utils import canonical_item_url

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchHit:
    url: str
    price: float
    title: str


class SearchResultsPage(BasePage):
    # Result cards that contain a real /itm/ link (skips empty promo tiles).
    ITEM_CARDS_XPATH = (
        "//li[(contains(@class,'s-item') or contains(@class,'s-card') "
        "or contains(@class,'brwrvr__item-card')) and .//a[contains(@href,'/itm/')]]"
        " | //div[contains(@class,'s-card') and .//a[contains(@href,'/itm/')]]"
    )
    # Listing URL inside one card.
    ITEM_LINK_XPATH = ".//a[contains(@href,'/itm/')]"
    # Displayed price node inside one card (current or discounted).
    ITEM_PRICE_XPATH = (
        ".//*[contains(@class,'s-item__price') or contains(@class,'s-card__price') "
        "or contains(@class,'s-item__discounted-price')]"
    )
    # Pagination next control.
    NEXT_PAGE = (
        "a.pagination__next, a[aria-label*='next search page' i], a[type='next']"
    )
    # Left-rail max price field.
    MAX_PRICE_INPUT = "input[aria-label*='Maximum' i], input[aria-label*='Max' i]"
    # Left-rail min price field.
    MIN_PRICE_INPUT = "input[aria-label*='Minimum' i], input[aria-label*='Min' i]"
    # Submit control next to the price range inputs.
    PRICE_SUBMIT = (
        "button[aria-label*='Submit price' i], button[aria-label*='Apply' i], "
        "button.x-textrange__button, input[aria-label*='Submit price' i]"
    )

    def __init__(self, page: Page) -> None:
        super().__init__(page)

    def apply_buy_it_now_filter(self) -> None:
        """Check Buy It Now when the sidebar checkbox is present so listings can go to cart."""
        self.dismiss_overlays()
        checkbox = self.page.locator("input[aria-label='Buy It Now']").first
        if self.visible(checkbox, timeout=1500) and not checkbox.is_checked():
            checkbox.check()
            self.wait_for_network_idle()
            logger.info("Applied Buy It Now filter via checkbox")

    def recover_from_error(self) -> None:
        """Leave eBay's Error Page via the homepage link, or navigate home directly.

        The error page includes a link back to ebay.com. Clicking it is more
        reliable than staying on the blocked response and searching again.
        """
        home_link = self.page.locator(".status--container a, .error-header a, a[href='https://www.ebay.com/']").first
        if self.visible(home_link, timeout=2000):
            home_link.click()
            self.page.wait_for_load_state("domcontentloaded")
            self.dismiss_overlays()
            logger.info("Recovered from error page via homepage link")
            return
        self.goto(self.settings.base_url)

    def apply_max_price_filter(self, max_price: float) -> None:
        """Fill the on-page max price filter when it exists; otherwise filter cards in code."""
        self.dismiss_overlays()
        max_input = self.page.locator(self.MAX_PRICE_INPUT).first
        if not self.visible(max_input, timeout=4000):
            logger.info("Price filter inputs were not visible; filtering results in code")
            return
        max_input.scroll_into_view_if_needed()
        max_input.fill(str(int(max_price)))
        min_input = self.page.locator(self.MIN_PRICE_INPUT).first
        if self.visible(min_input, timeout=1000):
            current = min_input.input_value()
            if not current:
                min_input.fill("0")
        submitted = self.click_first_visible(self.PRICE_SUBMIT.split(", "), timeout=2000)
        if not submitted:
            max_input.press("Enter")
        self.wait_for_network_idle()
        if self.is_error_page():
            logger.warning("Price filter submission hit an error page; going back")
            self.page.go_back(wait_until="domcontentloaded")
            self.dismiss_overlays()
            return
        logger.info("Applied max price filter via UI: %s", max_price)

    def collect_items_under_price(self, max_price: float, seen_ids: set[str]) -> list[SearchHit]:
        """Return priced /itm/ listings on the current page that are at or below max_price."""
        try:
            self.page.wait_for_selector("li.s-card, li.s-item, a[href*='/itm/']", timeout=15000)
        except PlaywrightTimeoutError:
            logger.warning("No result cards became visible on %s", self.page.url)
        cards = self.page.locator(f"xpath={self.ITEM_CARDS_XPATH}")
        count = cards.count()
        logger.info("Found %s result cards on the current page", count)
        hits: list[SearchHit] = []
        for index in range(count):
            card = cards.nth(index)
            hit = self._parse_card(card, max_price, seen_ids)
            if hit:
                hits.append(hit)
                seen_ids.add(hit.url)
        return hits

    def go_to_next_page(self) -> bool:
        """Click Next when pagination exists and is enabled."""
        next_link = self.page.locator(self.NEXT_PAGE).first
        if not self.visible(next_link, timeout=2500):
            logger.info("No pagination control found")
            return False
        aria_disabled = (next_link.get_attribute("aria-disabled") or "").lower()
        class_name = next_link.get_attribute("class") or ""
        if aria_disabled == "true" or "disabled" in class_name:
            logger.info("Next page control is disabled")
            return False
        try:
            next_link.click()
            self.page.wait_for_load_state("domcontentloaded")
            self.dismiss_overlays()
            self.wait_for_network_idle()
            logger.info("Moved to next search page")
            return True
        except PlaywrightTimeoutError:
            return False

    def _parse_card(self, card: Locator, max_price: float, seen_ids: set[str]) -> SearchHit | None:
        """Extract a canonical item URL and price from one result card, or skip it."""
        try:
            link = card.locator(f"xpath={self.ITEM_LINK_XPATH}").first
            href = link.get_attribute("href") or ""
            url = canonical_item_url(href)
            if not url or url in seen_ids:
                return None
            title = (link.inner_text() or "").strip()
            if "shop on ebay" in title.lower():
                return None
            price_text = ""
            price_el = card.locator(f"xpath={self.ITEM_PRICE_XPATH}").first
            if self.visible(price_el, timeout=500):
                price_text = price_el.inner_text()
            if not price_text:
                price_text = card.inner_text()
            price = parse_listing_price(price_text)
            if price is None or price > max_price:
                return None
            return SearchHit(url=url, price=price, title=title or url)
        except PlaywrightTimeoutError:
            return None
