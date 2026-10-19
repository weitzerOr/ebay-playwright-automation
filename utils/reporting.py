from __future__ import annotations

from datetime import datetime
from pathlib import Path

import allure
from playwright.sync_api import Page

from config.settings import get_settings


def _stamp(name: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)
    return f"{safe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def attach_screenshot(page: Page, name: str) -> Path:
    settings = get_settings()
    path = settings.screenshot_dir / f"{_stamp(name)}.png"
    page.screenshot(path=str(path), full_page=True)
    allure.attach.file(str(path), name=name, attachment_type=allure.attachment_type.PNG)
    return path


def attach_text(name: str, body: str) -> None:
    allure.attach(body, name=name, attachment_type=allure.attachment_type.TEXT)
