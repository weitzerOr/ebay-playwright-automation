from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")


def _as_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, default: int) -> int:
    if not value:
        return default
    return int(value)


@dataclass(frozen=True)
class Settings:
    base_url: str
    auth_mode: str
    ebay_email: str
    ebay_password: str
    headless: bool
    slow_mo_ms: int
    timeout_ms: int
    browser_channel: str
    random_seed: int | None
    max_search_pages: int
    screenshot_dir: Path
    traces_dir: Path

    @property
    def cart_url(self) -> str:
        return "https://cart.ebay.com/"

    @property
    def sign_in_url(self) -> str:
        return "https://signin.ebay.com/"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    seed = os.getenv("RANDOM_SEED", "").strip()
    screenshot_dir = ROOT_DIR / "reports" / "screenshots"
    traces_dir = ROOT_DIR / "reports" / "traces"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    traces_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        base_url=os.getenv("EBAY_BASE_URL", "https://www.ebay.com").rstrip("/"),
        auth_mode=os.getenv("EBAY_AUTH_MODE", "guest").strip().lower(),
        ebay_email=os.getenv("EBAY_EMAIL", "").strip(),
        ebay_password=os.getenv("EBAY_PASSWORD", "").strip(),
        headless=_as_bool(os.getenv("HEADLESS"), default=False),
        slow_mo_ms=_as_int(os.getenv("SLOW_MO_MS"), 0),
        timeout_ms=_as_int(os.getenv("TIMEOUT_MS"), 45_000),
        browser_channel=os.getenv("BROWSER_CHANNEL", "").strip(),
        random_seed=int(seed) if seed else None,
        max_search_pages=_as_int(os.getenv("MAX_SEARCH_PAGES"), 8),
        screenshot_dir=screenshot_dir,
        traces_dir=traces_dir,
    )
