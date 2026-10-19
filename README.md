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
pytest -m e2e --alluredir=allure-results           # live ebay.com flow
pytest -n 2 -m e2e                                 # a couple of live browsers at once
pytest --video=off                                 # skip the flow recording
HEADLESS=true pytest --alluredir=allure-results    # headless (often blocked by eBay)
```

Every test in `tests/` is an end-to-end run against ebay.com.

Parallel workers come from [pytest-xdist](https://pytest-xdist.readthedocs.io/). `-n 2` starts two workers. Each worker has its own browser, so tests must stay independent (they already get a fresh `page`). Live eBay often blocks many browsers from one machine; keep parallelism low.

Each test records a `.webm` of the flow and attaches it to that test in Allure. Recording is on by default (`--video=on` in `pytest.ini`). `--video=off` disables it for that run.

Serve the report without generating a static folder:

```bash
allure serve allure-results
```

Screenshots from each added item and the cart are stored in `reports/screenshots/` and attached to Allure. JUnit XML is written to `reports/junit.xml`.

An example of a finished run is checked in at [`run-report.html`](run-report.html) in the repository root. Open that file in a browser. It is a single HTML report (statuses, steps, text attachments, and compressed screenshots) and does not include the raw Allure output.

`allure-results/` and `allure-report/` are gitignored, so those folders stay out of the repo. To refresh the example after a new pytest run:

```bash
python scripts/build_run_report.py
```

That overwrites `run-report.html` in the repository root. Commit that file on its own.

## Docker

The image includes Playwright browsers, xvfb (so Chromium can run “headed” without a real display), and the Allure CLI. Start Docker Desktop first.

```bash
cp .env.example .env
docker compose build
docker compose run --rm tests
```

That runs the live eBay suite. Results are written to the host:

- `allure-results/` — raw Allure data
- `reports/` — screenshots and JUnit XML
- `allure-report/` — filled after the next command

Useful variants:

```bash
docker compose run --rm tests pytest -m e2e
docker compose run --rm tests pytest -n 2 -m e2e
docker compose run --rm tests pytest --video=off
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

- **eBay e2e** — the whole suite, against the live site on GitHub-hosted runners. Marked `continue-on-error` because eBay often blocks datacenter IPs. Allure results and screenshots are uploaded as artifacts either way.

Download the `e2e-allure-results` artifact from the workflow run, then locally:

```bash
allure generate allure-results -o allure-report --clean
allure open allure-report
```

## Architecture

A detailed write-up of the layers, the run sequence, and where a change belongs is in [`docs/architecture.pdf`](docs/architecture.pdf).

```
config/          Environment-driven settings (see Configuration)
data/            External scenario JSON (see Scenarios)
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

## Configuration

Runtime settings come from the environment. `config/settings.py` loads `.env` from the repo root (via `python-dotenv`) and exposes them through `get_settings()`. Copy `.env.example` to `.env` and edit that file for local runs. A variable already set in the process (Docker Compose, CI, or the shell) takes precedence over `.env`.

| Variable | Default | What it controls |
| --- | --- | --- |
| `EBAY_BASE_URL` | `https://www.ebay.com` | Site the suite opens |
| `EBAY_AUTH_MODE` | `guest` | Default for `authenticate()` when no mode is passed. The e2e test passes the scenario's `auth_mode` instead (see Scenarios) |
| `EBAY_EMAIL` / `EBAY_PASSWORD` | empty | Credentials for `login` mode |
| `HEADLESS` | `false` | Headed Chromium by default. `true` / `1` / `yes` / `on` turn headless on |
| `SLOW_MO_MS` | `0` | Playwright slow-motion delay, in milliseconds |
| `TIMEOUT_MS` | `45000` | Default page and navigation timeout |
| `BROWSER_CHANNEL` | empty | Set to `chrome` to drive the installed Google Chrome instead of Playwright's Chromium |
| `RANDOM_SEED` | empty | Seed for variant picks (size, color). Empty means a new random sequence each run |
| `MAX_SEARCH_PAGES` | `8` | How many search-result pages to walk while collecting listings |

`conftest.py` applies those settings to the browser: viewport 1440×900, locale `en-US`, the timeout above, headless/slow-motion, and the optional Chrome channel. In Docker or CI it also adds `--no-sandbox` and `--disable-gpu`.

`pytest.ini` is the runner config: tests live under `tests/`, every test is marked `e2e` (live ebay.com), Allure results go to `allure-results/`, flow video is recorded (`--video=on`), failure screenshots and traces are kept, and JUnit XML is written to `reports/junit.xml`. Pass `--video=off` to skip recording. Pass `-n 2` to run a couple of browsers in parallel.

Screenshots land in `reports/screenshots/` and traces in `reports/traces/`. Those folders are created when settings load.

## Scenarios

`data/test_data.json` is an external scenario injector. The e2e test does not hardcode the search. At collection time `utils/data_loader.py` (`load_test_scenarios`) reads the `scenarios` array, and `tests/test_ebay_shopping_flow.py` parametrizes one test per object. The pytest node id is the scenario `id` (or the query if `id` is omitted).

Add, remove, or edit objects in that file to change what runs. The Python test stays the same. Docker mounts `./data` read-only into the container, so the host file is what the container executes.

```json
{
  "scenarios": [
    {
      "id": "shoes_under_220",
      "query": "shoes",
      "max_price": 220,
      "limit": 5,
      "auth_mode": "guest"
    }
  ]
}
```

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | no | Name shown in pytest and Allure. Falls back to `query` |
| `query` | yes | Text typed into eBay search |
| `max_price` | yes | Numeric cap. Applied to the price the site displays, in the site currency, with no conversion |
| `limit` | no | How many listing URLs to collect. Default `5` |
| `auth_mode` | no | `guest` (default) or `login`. `login` also needs `EBAY_EMAIL` and `EBAY_PASSWORD` in the config above |

The file must contain a non-empty `scenarios` list. Pytest fails at collection if the list is missing or empty.

## Adding tests

How to add a test is in [`.claude/skills/add-ebay-tests/SKILL.md`](.claude/skills/add-ebay-tests/SKILL.md). Cursor and Claude Code both load that one file. Another search or budget is a new object in `data/test_data.json`. New page behavior goes on a page object, then a thin test. The skill also says to enable the Playwright MCP before writing locators.

## Limitations / assumptions

- **Guest checkout** is the default. Full eBay login is implemented but is often blocked by captcha / 2FA.
- **Headed Chrome** is the default. eBay frequently serves an error page to headless / non-browser clients. Docker uses xvfb as a virtual display for the same reason.
- **Currency** follows the site locale (this environment shows **ILS**). The numeric cap from the JSON file is applied to the displayed currency, not converted.
- The cart assertion uses the **item subtotal** when possible, not grand total, so shipping and import charges do not fail a valid budget check.
- Listings without Add to cart (auction-only, offer-only, missing variants) are skipped. The test fails only if nothing can be added.
- Live eBay markup, ads, and availability change constantly; locators have fallbacks, but the site remains a moving target.
