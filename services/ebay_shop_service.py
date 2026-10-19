from __future__ import annotations

import logging
import random

import allure
from playwright.sync_api import Page

from config.settings import get_settings
from pages.cart_page import CartPage
from pages.home_page import HomePage
from pages.item_page import ItemPage
from pages.search_results_page import SearchResultsPage
from pages.sign_in_page import SignInPage
from utils.reporting import attach_screenshot, attach_text

logger = logging.getLogger(__name__)


class EbayShopService:
    """Business flows composed from page objects. One class, four public actions."""

    def __init__(self, page: Page) -> None:
        """Wire page objects used by the four business actions."""
        self.page = page
        self.settings = get_settings()
        self.rng = random.Random(self.settings.random_seed)
        self.home_page = HomePage(page)
        self.search_page = SearchResultsPage(page)
        self.item_page = ItemPage(page, self.rng)
        self.cart_page = CartPage(page)
        self.sign_in_page = SignInPage(page)
        self._last_search_url: str | None = None
        self.added_item_urls: list[str] = []

    @allure.step("Authenticate as {mode}")
    def authenticate(self, mode: str | None = None) -> None:
        """Open eBay as guest, or sign in when mode is login."""
        auth_mode = (mode or self.settings.auth_mode).lower()
        if auth_mode == "guest":
            if "ebay.com" not in self.page.url or self.home_page.is_error_page():
                self.home_page.open()
            else:
                self.home_page.dismiss_overlays()
            attach_text("auth_mode", "guest")
            return
        if auth_mode == "login":
            self.sign_in_page.login(self.settings.ebay_email, self.settings.ebay_password)
            return
        raise ValueError(f"Unsupported auth mode: {auth_mode}")

    @allure.step("Search '{query}' under ${max_price} (limit={limit})")
    def search_items_by_name_under_price(
        self,
        query: str,
        max_price: float,
        limit: int = 5,
    ) -> list[str]:
        """Search, apply the price cap, and return up to `limit` listing URLs at or below it."""
        if self.search_page.is_error_page() or "ebay.com" not in self.page.url:
            self.home_page.open()
        self.home_page.search(query)
        if self.search_page.is_error_page():
            self.search_page.recover_from_error()
            self.home_page.search(query)
        self.search_page.apply_max_price_filter(max_price)
        self.search_page.apply_buy_it_now_filter()
        self._last_search_url = self.page.url
        attach_screenshot(self.page, f"search_results_{query}")

        urls: list[str] = []
        seen: set[str] = set()
        pages_visited = 0

        while len(urls) < limit and pages_visited < self.settings.max_search_pages:
            pages_visited += 1
            hits = self.search_page.collect_items_under_price(max_price, seen)
            for hit in hits:
                urls.append(hit.url)
                logger.info("Collected %s at $%s", hit.url, hit.price)
                if len(urls) >= limit:
                    break
            if len(urls) >= limit:
                break
            if not self.search_page.go_to_next_page():
                break

        attach_text("item_urls", "\n".join(urls) if urls else "(none)")
        logger.info("Returning %s item URLs (requested %s)", len(urls), limit)
        return urls

    @allure.step("Add items to cart")
    def add_items_to_cart(self, urls: list[str]) -> list[str]:
        """Open each listing, add it to the cart when possible, and screenshot the result."""
        added: list[str] = []
        for index, url in enumerate(urls, start=1):
            with allure.step(f"Add item {index}/{len(urls)}: {url}"):
                self.item_page.open(url)
                success = self.item_page.add_to_cart()
                attach_screenshot(self.page, f"added_item_{index}")
                if success:
                    added.append(url)
                else:
                    logger.warning("Skipping item that cannot be added to cart: %s", url)
                    attach_text(f"skipped_item_{index}", url)
                if self._last_search_url:
                    self.page.goto(self._last_search_url, wait_until="domcontentloaded")
                    self.search_page.dismiss_overlays()
        if not added:
            raise AssertionError("None of the collected listings could be added to the cart")
        self.added_item_urls = added
        return added

    @allure.step("Assert cart total does not exceed ${budget_per_item} x {items_count}")
    def assert_cart_total_not_exceeds(self, budget_per_item: float, items_count: int) -> None:
        """Assert the cart item total is at most budget_per_item * items_count."""
        self.cart_page.open()
        attach_screenshot(self.page, "cart_page")
        total = self.cart_page.read_item_subtotal()
        threshold = budget_per_item * items_count
        attach_text(
            "cart_assertion",
            f"subtotal={total}\nthreshold={threshold}\nbudget_per_item={budget_per_item}\nitems={items_count}",
        )
        assert total <= threshold + 0.01, (
            f"Cart total {total:.2f} exceeds budget threshold {threshold:.2f} "
            f"({budget_per_item:.2f} x {items_count})"
        )
        logger.info("Cart subtotal %.2f is within threshold %.2f", total, threshold)
