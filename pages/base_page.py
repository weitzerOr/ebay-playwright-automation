from __future__ import annotations

import logging

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from config.settings import get_settings

logger = logging.getLogger(__name__)

# Fallback close/accept buttons for popups that intercept clicks.
# The shipping-address lightbox is closed separately via .address-dialog__lightbox.
# Remaining entries cover cookie banners, guest prompts, and leftover eBay dialogs
# that appear depending on locale and session.
_OVERLAY_SELECTORS = [
    "button.lightbox-dialog__close",
    "button[aria-label='Dismiss']",
    "button[aria-label='Close dialogue']",
    "button[aria-label='Close']",
    "button[aria-label='Close dialog']",
    "button[aria-label='Close the survey']",
    "#gdpr-banner-accept",
    "button#gdpr-banner-accept",
]


class BasePage:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.settings = get_settings()

    def goto(self, url: str) -> None:
        """Open a URL and dismiss blocking dialogs."""
        logger.info("Opening %s", url)
        self.page.goto(url, wait_until="domcontentloaded")
        self.page.wait_for_timeout(800)
        self.dismiss_overlays()

    def dismiss_overlays(self) -> None:
        """Close the shipping lightbox first, then any leftover popup close buttons."""
        address_dialog = self.page.locator(".address-dialog__lightbox").first
        try:
            if address_dialog.is_visible(timeout=800):
                closer = address_dialog.locator("button.lightbox-dialog__close, button[aria-label='Dismiss']").first
                closer.click(timeout=2000)
                address_dialog.wait_for(state="hidden", timeout=5000)
                logger.info("Closed shipping address dialog")
        except PlaywrightError:
            try:
                self.page.keyboard.press("Escape")
            except PlaywrightError:
                pass
        for selector in _OVERLAY_SELECTORS:
            locator = self.page.locator(selector).first
            try:
                if locator.is_visible(timeout=800):
                    locator.click(timeout=1500)
                    logger.info("Dismissed overlay via %s", selector)
            except PlaywrightError:
                continue

    def visible(self, locator: Locator, timeout: int = 2500) -> bool:
        """Return True if the locator becomes visible before the timeout."""
        try:
            locator.first.wait_for(state="visible", timeout=timeout)
            return True
        except PlaywrightTimeoutError:
            return False

    def click_first_visible(self, selectors: list[str], timeout: int = 4000) -> bool:
        """Click the first selector that is visible; force-click if a overlay intercepts."""
        for selector in selectors:
            locator = self.page.locator(selector).first
            if self.visible(locator, timeout=timeout):
                try:
                    locator.click(timeout=5000)
                except PlaywrightError:
                    locator.click(force=True, timeout=3000)
                return True
        return False

    def is_error_page(self) -> bool:
        """Detect eBay's generic 'Error Page' response."""
        return "error page" in (self.page.title() or "").lower()

    def wait_for_network_idle(self, timeout: int = 8000) -> None:
        """Wait for network idle, falling back to DOM ready if the page keeps polling."""
        try:
            self.page.wait_for_load_state("networkidle", timeout=timeout)
        except PlaywrightTimeoutError:
            self.page.wait_for_load_state("domcontentloaded")
