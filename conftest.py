from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Generator

import allure
import pytest
from playwright.sync_api import Page

from config.settings import ROOT_DIR, get_settings
from services.ebay_shop_service import EbayShopService
from utils.reporting import attach_screenshot


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    args = {
        **browser_type_launch_args,
        "slow_mo": settings.slow_mo_ms,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
        ],
    }
    if os.getenv("RUNNING_IN_DOCKER") or os.getenv("CI"):
        args["args"].extend(["--no-sandbox", "--disable-gpu"])
    args["headless"] = settings.headless
    if settings.browser_channel:
        args["channel"] = settings.browser_channel
    return args


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict[str, Any]) -> dict[str, Any]:
    return {
        **browser_context_args,
        "viewport": {"width": 1440, "height": 900},
        "locale": "en-US",
        "timezone_id": "America/New_York",
        "user_agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "extra_http_headers": {"Accept-Language": "en-US,en;q=0.9"},
    }


@pytest.fixture(scope="session", autouse=True)
def _allure_environment() -> None:
    settings = get_settings()
    env_dir = ROOT_DIR / "allure-results"
    env_dir.mkdir(parents=True, exist_ok=True)
    (ROOT_DIR / "reports").mkdir(parents=True, exist_ok=True)
    (env_dir / "environment.properties").write_text(
        "\n".join(
            [
                f"BaseURL={settings.base_url}",
                f"AuthMode={settings.auth_mode}",
                f"Headless={settings.headless}",
                "Browser=chromium",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


@pytest.fixture
def ebay_shop(page: Page) -> EbayShopService:
    timeout = get_settings().timeout_ms
    page.set_default_timeout(timeout)
    page.set_default_navigation_timeout(timeout)
    return EbayShopService(page)


def _attach_flow_videos(item: pytest.Item, report: pytest.TestReport) -> None:
    """Attach the Playwright .webm once the context has closed and the file exists."""
    root = Path(str(item.config.invocation_params.dir))
    for key, raw in getattr(report, "user_properties", []):
        if key != "playwright_video":
            continue
        path = Path(str(raw))
        if not path.is_file():
            path = root / path
        if path.is_file():
            allure.attach.file(str(path), name="recording", attachment_type=allure.attachment_type.WEBM)


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> Generator[None, None, None]:
    outcome = yield
    report = outcome.get_result()
    # Video is finalized during teardown, after pytest-playwright saves it.
    if report.when == "teardown":
        _attach_flow_videos(item, report)
        return
    if report.when != "call" or not report.failed:
        return
    page = item.funcargs.get("page")
    if isinstance(page, Page):
        attach_screenshot(page, "failure")
        allure.attach(page.url, name="page_url", attachment_type=allure.attachment_type.TEXT)
