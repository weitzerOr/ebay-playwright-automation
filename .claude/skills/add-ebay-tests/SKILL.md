---
name: add-ebay-tests
description: >-
  Add or extend eBay Playwright tests in this repo: JSON scenarios, page
  objects, EbayShopService, Allure video, and pytest-xdist. Use when adding a
  test, scenario, page object, or locator, or when the user mentions Playwright
  MCP, new e2e coverage, or test_data.json. This file is the shared rule for
  Cursor and Claude Code.
---

# Add tests

This is the one project rule for adding tests. Cursor loads it from `.claude/skills/` and Claude Code loads it from the same path. Do not copy it into a second rules file.

## Playwright MCP

Before writing or changing a locator, use the Playwright MCP (`@playwright/mcp`) and read a live snapshot of the page. If that MCP is not enabled, stop and tell the user to add it. Continue only after it is available. Do not invent eBay selectors.

Cursor — `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["-y", "@playwright/mcp@latest"]
    }
  }
}
```

Claude Code — `.mcp.json` at the repo root, with the same `mcpServers` block.

## Where the case goes

The existing flow is search, add to cart, assert the cart total. Another query or budget is a new object in `data/test_data.json`. Do not copy `tests/test_ebay_shopping_flow.py`.

New behavior:

1. Put the locator and the action on the matching class in `pages/`. Use `BasePage`: `visible`, `click_first_visible`, `dismiss_overlays`, `is_error_page`.
2. Add a method on `EbayShopService` with `@allure.step` only when the test should call one business action.
3. Add a thin test under `tests/` and mark it `@pytest.mark.e2e`. Every test drives live ebay.com. Do not add offline tests.
4. Read inputs from JSON (`utils/data_loader.py` or a new file in `data/`). Keep queries and prices out of the test body.

## Rules

- Each test gets its own `page` fixture. Do not share a page, cookies, or cart across tests. That is what makes `pytest -n auto` safe.
- Flow video is already on (`--video=on` in `pytest.ini`) and is attached to Allure as `recording`. Do not disable it inside a test. A local run can pass `pytest --video=off`.
- Do not add `time.sleep`. Use the waits already on `BasePage`.
- A document title that contains "Error Page" is eBay blocking the client. Recover with `is_error_page`, `recover_from_error`, or one reload. Do not treat that page as success.
- Default auth is guest. Login needs `EBAY_EMAIL` and `EBAY_PASSWORD` and often stops on captcha.
- Assert the outcome (listing URLs, cart total, parsed price). Creating a locator is not an assertion.
