# eBay Playwright Automation

End-to-end Playwright tests for [ebay.com](https://www.ebay.com/): search by name with a max price, add listings to the cart, and assert the cart total stays within budget.

## Prerequisites

- Python 3.10+ (local runs)
- Google Chrome or Chromium (Playwright installs Chromium)
- [Allure Commandline](https://allurereport.org/docs/install/) to open the HTML report (`brew install allure` on macOS)
- Docker Desktop / Docker Compose v2 (container runs)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
```

## How to run (pytest + Allure)

Install Allure CLI once (`brew install allure` on macOS). Pytest already writes results to `allure-results/` via `pytest.ini`.

```bash
source .venv/bin/activate
pytest --alluredir=allure-results
allure generate allure-results -o allure-report --clean
allure open allure-report
```

That runs the full suite, then opens the HTML report in a browser.

Useful pytest variants:

```bash
pytest -m unit --alluredir=allure-results          # offline price-parser tests
pytest -m e2e --alluredir=allure-results           # live ebay.com flow
HEADLESS=true pytest --alluredir=allure-results    # headless (often blocked by eBay)
```

Serve the report without generating a static folder:

```bash
allure serve allure-results
```

Screenshots from each added item and the cart are stored in `reports/screenshots/` and attached to Allure. JUnit XML is written to `reports/junit.xml`.

## Docker

The image includes Playwright browsers, xvfb (so Chromium can run “headed” without a real display), and the Allure CLI. Start Docker Desktop first.

```bash
cp .env.example .env
docker compose build
docker compose run --rm tests
```

That runs the full pytest suite (unit + live eBay e2e). Results are written to the host:

- `allure-results/` — raw Allure data
- `reports/` — screenshots and JUnit XML
- `allure-report/` — filled after the next command

Useful variants:

```bash
docker compose run --rm tests pytest -m unit
docker compose run --rm tests pytest -m e2e
HEADLESS=true docker compose run --rm tests
```

Open the Allure report in a browser (no Allure install on the host):

```bash
docker compose run --rm tests
docker compose up allure-ui
```

Then open [http://localhost:5050](http://localhost:5050). Stop the server with Ctrl+C.

To write a static HTML report to `allure-report/` instead:

```bash
docker compose run --rm allure
```

Compose defaults to `HEADLESS=false` and wraps pytest with xvfb because eBay often blocks classic headless Chrome. Datacenter IPs can still receive eBay’s error page; if that happens, run the suite on the host instead.

Raw Allure results are written to `allure-results/`. Screenshots from each added item and the cart are stored in `reports/screenshots/` and attached to Allure.

## GitHub Actions

`.github/workflows/tests.yml` runs on push to `main`, pull requests, and manual **Run workflow**.

- **Unit tests** — required. Offline price-parser tests.
- **eBay e2e** — live site against GitHub-hosted runners. Marked `continue-on-error` because eBay often blocks datacenter IPs. Allure results and screenshots are uploaded as artifacts either way.

Download the `e2e-allure-results` artifact from the workflow run, then locally:

```bash
allure generate allure-results -o allure-report --clean
allure open allure-report
```

## Architecture

```
config/          Environment-driven settings
data/            JSON scenarios (query, max price, limit, auth mode)
pages/           Page Object Model (home, search, item, cart, sign-in)
services/        Business flows composed from page objects
utils/           Price parser, reporting, URL helpers, data loader
tests/           Pytest + Allure
```

`EbayShopService` exposes the four required actions:

1. `authenticate` — guest by default; optional login via `EBAY_EMAIL` / `EBAY_PASSWORD`
2. `search_items_by_name_under_price(query, max_price, limit=5)` — search, apply price + Buy It Now filters, collect listing URLs with XPath, paginate if needed
3. `add_items_to_cart(urls)` — open each item, pick random available variants, click Add to cart, screenshot
4. `assert_cart_total_not_exceeds(budget_per_item, items_count)` — read the cart item subtotal and assert it is `<= budget_per_item * items_count`

Change search data in `data/test_data.json` without touching test code.

## Limitations / assumptions

- **Guest checkout** is the default. Full eBay login is implemented but is often blocked by captcha / 2FA.
- **Headed Chrome** is the default. eBay frequently serves an error page to headless / non-browser clients. Docker uses xvfb as a virtual display for the same reason.
- **Currency** follows the site locale (this environment shows **ILS**). The numeric cap from the JSON file is applied to the displayed currency, not converted.
- The cart assertion uses the **item subtotal** when possible, not grand total, so shipping and import charges do not fail a valid budget check.
- Listings without Add to cart (auction-only, offer-only, missing variants) are skipped. The test fails only if nothing can be added.
- Live eBay markup, ads, and availability change constantly; locators have fallbacks, but the site remains a moving target.
