from __future__ import annotations

import logging

from playwright.sync_api import Page

from pages.base_page import BasePage

logger = logging.getLogger(__name__)


class SignInPage(BasePage):
    # Email / username field on the first sign-in step.
    USER_INPUT = "#userid, input[name='userid'], input[type='email']"
    # Continue after entering the user id.
    CONTINUE_BUTTON = "#signin-continue-btn, button#signin-continue-btn"
    # Password field on the second sign-in step.
    PASSWORD_INPUT = "#pass, input[name='pass'], input[type='password']"
    # Final sign-in submit.
    SIGN_IN_BUTTON = "#sgnBt, button#sgnBt"

    def __init__(self, page: Page) -> None:
        super().__init__(page)

    def login(self, email: str, password: str) -> None:
        """Complete eBay's two-step sign-in. Fails if captcha/2FA keeps the user on signin."""
        if not email or not password:
            raise ValueError("EBAY_EMAIL and EBAY_PASSWORD are required for login mode")
        logger.info("Authenticating as %s", email)
        self.goto(self.settings.sign_in_url)
        self.page.locator(self.USER_INPUT).first.fill(email)
        self.click_first_visible(self.CONTINUE_BUTTON.split(", "))
        self.page.locator(self.PASSWORD_INPUT).first.wait_for(state="visible")
        self.page.locator(self.PASSWORD_INPUT).first.fill(password)
        self.click_first_visible(self.SIGN_IN_BUTTON.split(", "))
        self.wait_for_network_idle()
        if "signin" in self.page.url.lower():
            raise RuntimeError(
                "eBay sign-in did not complete. Captcha or 2FA may be required; use guest mode."
            )
