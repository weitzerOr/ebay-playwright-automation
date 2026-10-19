from __future__ import annotations

import logging

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

from pages.base_page import BasePage

logger = logging.getLogger(__name__)


class HomePage(BasePage):
    # Header search box. Tried in order: current id, classic name, generic search input.
    SEARCH_INPUT = "#gh-ac, input[name='_nkw'], input[type='search']"
    # Header search submit. Tried in order: current id, legacy id, button class.
    SEARCH_BUTTON = "#gh-search-btn, #gh-btn, button.gh-search-button"

    def __init__(self, page: Page) -> None:
        super().__init__(page)

    def open(self) -> None:
        """Open ebay.com and reload once if the error page appears."""
        self.goto(self.settings.base_url)
        # Same eBay "Error Page" as BasePage.is_error_page; one reload often clears it.
        if "Error Page" in (self.page.title() or ""):
            self.page.reload(wait_until="domcontentloaded")
            self.dismiss_overlays()

    def search(self, query: str) -> None:
        """Type the query in the header search box and wait for the results page."""
        self.dismiss_overlays()
        search_box = self.page.locator(self.SEARCH_INPUT).first
        search_box.wait_for(state="visible")
        search_box.click(force=True)
        search_box.fill(query)
        logger.info("Searching for %r", query)
        self.dismiss_overlays()
        try:
            if not self.click_first_visible(self.SEARCH_BUTTON.split(", "), timeout=2000):
                search_box.press("Enter")
        except PlaywrightError:
            search_box.press("Enter")
        self.page.wait_for_url("**/sch/**", timeout=self.settings.timeout_ms)
        self.dismiss_overlays()
        try:
            self.page.wait_for_selector("li.s-card, li.s-item, a[href*='/itm/']", timeout=20000)
        except PlaywrightError:
            logger.warning("Search results did not render listing cards")
