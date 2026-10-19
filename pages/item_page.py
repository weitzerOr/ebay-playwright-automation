from __future__ import annotations

import logging
import random

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from pages.base_page import BasePage

logger = logging.getLogger(__name__)


class ItemPage(BasePage):
    # Add to cart CTA. Tried in order: classic id, vim test id, buy-box action, secondary CTA.
    ADD_TO_CART = (
        "a#atcBtn_btn_1, [data-testid='x-atc-action'] a, [data-testid='x-atc-action'] button, "
        "div.x-atc-action a, div.x-atc-action button, "
        "#mainContent a[data-testid='ux-call-to-action'].fake-btn--secondary"
    )
    # Overlay shown after a successful add (lightbox or legacy ATC redesign).
    CONFIRMATION = (
        "[data-testid='lightbox-dialog'], .lightbox-dialog--show, "
        ".vi-overlayTitleBar, [id*='atcRedesignId']"
    )
    # Size/color <select> controls inside the buy box.
    NATIVE_SELECTS = "#mainContent select.listbox__native, #mainContent .x-msku select"
    # Custom listbox trigger buttons for MSKU variants.
    LISTBOX_BUTTON = (
        "#mainContent div.listbox-button button, "
        "#mainContent button.listbox-button__control"
    )
    # Options inside an open listbox.
    LISTBOX_OPTION = "[role='option']:visible, div.listbox__option:visible"

    def __init__(self, page: Page, rng: random.Random) -> None:
        super().__init__(page)
        self.rng = rng

    def open(self, url: str) -> None:
        """Open a listing URL."""
        self.goto(url)
        self.wait_for_network_idle()

    def add_to_cart(self) -> bool:
        """Select required variants if needed, click Add to cart, and close the confirmation."""
        self.dismiss_overlays()
        self.select_random_variants()
        self.dismiss_overlays()
        add_button = self._add_to_cart_locator()
        if not add_button:
            logger.warning("No Add to cart action on %s", self.page.url)
            return False
        add_button.click()
        self.page.wait_for_timeout(800)
        if self._has_unselected_variants():
            logger.info("Variant required after Add to cart; retrying selection")
            self.select_random_variants()
            add_button = self._add_to_cart_locator()
            if not add_button:
                return False
            add_button.click()
        self._acknowledge_confirmation()
        logger.info("Clicked Add to cart on %s", self.page.url)
        return True

    def select_random_variants(self) -> None:
        """Pick a random available value for each size/color/style control."""
        self._select_native_dropdowns()
        self._select_listboxes()

    def _add_to_cart_locator(self) -> Locator | None:
        """Return the first visible Add to cart control from ADD_TO_CART."""
        for selector in self.ADD_TO_CART.split(", "):
            locator = self.page.locator(selector).first
            if self.visible(locator, timeout=2500):
                return locator
        return None

    def _has_unselected_variants(self) -> bool:
        """True when a variant control is still invalid or labeled as unselected."""
        invalid = self.page.locator(
            "#mainContent [aria-invalid='true'], #mainContent .x-msku [class*='error']"
        ).first
        if self.visible(invalid, timeout=800):
            return True
        buttons = self.page.locator(self.LISTBOX_BUTTON)
        for index in range(buttons.count()):
            button = buttons.nth(index)
            if not self.visible(button, timeout=300):
                continue
            label = (button.get_attribute("aria-label") or "").lower()
            if "select" in label:
                return True
        return False

    def _select_native_dropdowns(self) -> None:
        """Choose a random enabled <option> on each native variant <select>."""
        selects = self.page.locator(self.NATIVE_SELECTS)
        for index in range(selects.count()):
            select = selects.nth(index)
            if not self.visible(select, timeout=800):
                continue
            enabled_values: list[str] = []
            for option in select.locator("option").all():
                value = option.get_attribute("value") or ""
                disabled = option.get_attribute("disabled")
                label = (option.inner_text() or "").strip().lower()
                if not value or value in {"-1", "0", ""} or disabled is not None:
                    continue
                if "select" in label or "please" in label:
                    continue
                enabled_values.append(value)
            if not enabled_values:
                continue
            choice = self.rng.choice(enabled_values)
            select.select_option(value=choice)
            logger.info("Selected native variant value %s", choice)
            self.page.wait_for_timeout(400)

    def _select_listboxes(self) -> None:
        """Open each unresolved listbox and click a random in-stock option."""
        for _ in range(4):
            buttons = self.page.locator(self.LISTBOX_BUTTON)
            unresolved = []
            for index in range(buttons.count()):
                button = buttons.nth(index)
                if not self.visible(button, timeout=500):
                    continue
                label = (button.get_attribute("aria-label") or button.inner_text() or "").lower()
                if "select" in label or "please select" in label or label.strip() in {"", "size", "color", "width"}:
                    unresolved.append(button)
            if not unresolved:
                return
            button = unresolved[0]
            try:
                button.click()
                self.page.wait_for_timeout(300)
                options = self.page.locator(self.LISTBOX_OPTION)
                enabled: list[Locator] = []
                for index in range(options.count()):
                    option = options.nth(index)
                    text = (option.inner_text() or "").strip()
                    class_name = option.get_attribute("class") or ""
                    aria_disabled = (option.get_attribute("aria-disabled") or "").lower()
                    if not text or "select" in text.lower():
                        continue
                    if "disabled" in class_name or aria_disabled == "true":
                        continue
                    if "out of stock" in text.lower() or "unavailable" in text.lower():
                        continue
                    enabled.append(option)
                if not enabled:
                    self.page.keyboard.press("Escape")
                    return
                choice = self.rng.choice(enabled)
                logger.info("Selected listbox variant %s", choice.inner_text().strip())
                choice.click()
                self.page.wait_for_timeout(500)
            except PlaywrightTimeoutError:
                self.page.keyboard.press("Escape")
                return

    def _acknowledge_confirmation(self) -> None:
        """Close the added-to-cart overlay, or wait if the page already moved to cart."""
        confirmation = self.page.locator(self.CONFIRMATION).first
        if self.visible(confirmation, timeout=5000):
            closer = confirmation.locator(
                "button.lightbox-dialog__close, button[aria-label='Dismiss'], button[aria-label='Close']"
            ).first
            if self.visible(closer, timeout=1500):
                closer.click()
            else:
                self.page.keyboard.press("Escape")
            return
        try:
            self.page.wait_for_url("**/cart**", timeout=4000)
        except PlaywrightTimeoutError:
            pass
