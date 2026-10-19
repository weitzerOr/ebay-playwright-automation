#!/usr/bin/env python3
"""Build one self-contained HTML report from Allure results.

Reads allure-results/, keeps the newest result for each test, and writes
run-report.html. The raw Allure files stay on disk and out of git.
"""

from __future__ import annotations

import base64
import html
import json
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "allure-results"
OUTPUT = ROOT / "run-report.html"
MAX_TEXT = 20_000


def latest_results() -> list[dict]:
    latest: dict[str, dict] = {}
    for path in RESULTS.glob("*-result.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        key = data.get("historyId") or data.get("name") or path.name
        current = latest.get(key)
        if current is None or (data.get("stop") or 0) >= (current.get("stop") or 0):
            latest[key] = data
    return sorted(latest.values(), key=lambda item: (item.get("fullName") or "", item.get("name") or ""))


def label_map(result: dict) -> dict[str, str]:
    return {item["name"]: item["value"] for item in result.get("labels") or [] if "name" in item}


def duration_seconds(result: dict) -> float:
    return max(0, ((result.get("stop") or 0) - (result.get("start") or 0)) / 1000)


def fmt_duration(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.0f} ms"
    return f"{seconds:.1f} s"


def fmt_time(millis: int | None) -> str:
    if not millis:
        return ""
    return datetime.fromtimestamp(millis / 1000).strftime("%Y-%m-%d %H:%M:%S")


def read_text(source: str) -> str:
    path = RESULTS / source
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > MAX_TEXT:
        return text[:MAX_TEXT] + "\n… truncated …"
    return text


def image_data_uri(source: str) -> str | None:
    path = RESULTS / source
    if not path.is_file():
        return None
    if shutil.which("sips"):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as handle:
            dest = Path(handle.name)
        try:
            subprocess.run(
                [
                    "sips",
                    "-s",
                    "format",
                    "jpeg",
                    "-s",
                    "formatOptions",
                    "55",
                    "-Z",
                    "1100",
                    str(path),
                    "--out",
                    str(dest),
                ],
                check=True,
                capture_output=True,
            )
            encoded = base64.b64encode(dest.read_bytes()).decode("ascii")
            return f"data:image/jpeg;base64,{encoded}"
        except (subprocess.CalledProcessError, OSError):
            return None
        finally:
            dest.unlink(missing_ok=True)
    raw = path.read_bytes()
    if len(raw) > 400_000:
        return None
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def render_attachments(attachments: list[dict]) -> str:
    chunks: list[str] = []
    for attachment in attachments:
        name = html.escape(str(attachment.get("name") or "attachment"))
        source = attachment.get("source") or ""
        mime = attachment.get("type") or ""
        if mime.startswith("image/"):
            uri = image_data_uri(source)
            if uri:
                chunks.append(
                    f'<figure><figcaption>{name}</figcaption><img alt="{name}" src="{uri}"></figure>'
                )
            continue
        if mime.startswith("text/") or source.endswith(".txt"):
            body = html.escape(read_text(source))
            if body.strip():
                chunks.append(f"<details open><summary>{name}</summary><pre>{body}</pre></details>")
    return "".join(chunks)


def render_steps(steps: list[dict]) -> str:
    if not steps:
        return ""
    items: list[str] = []
    for step in steps:
        name = html.escape(str(step.get("name") or "step"))
        status = html.escape(str(step.get("status") or ""))
        inner = render_steps(step.get("steps") or [])
        attached = render_attachments(step.get("attachments") or [])
        items.append(
            f'<li><span class="status {status}">{status}</span> {name}{attached}{inner}</li>'
        )
    return "<ol class=\"steps\">" + "".join(items) + "</ol>"


def render_result(result: dict) -> str:
    labels = label_map(result)
    status = html.escape(str(result.get("status") or "unknown"))
    name = html.escape(str(result.get("name") or "test"))
    suite = html.escape(labels.get("suite") or labels.get("package") or "")
    tag = html.escape(labels.get("tag") or "")
    started = html.escape(fmt_time(result.get("start")))
    params = result.get("parameters") or []
    param_html = ""
    if params:
        rows = "".join(
            f"<tr><th>{html.escape(str(item.get('name') or ''))}</th>"
            f"<td>{html.escape(str(item.get('value') or ''))}</td></tr>"
            for item in params
        )
        param_html = f"<table>{rows}</table>"
    details = result.get("statusDetails") or {}
    failure = ""
    message = details.get("message") or ""
    trace = details.get("trace") or ""
    if message or trace:
        failure = (
            f"<pre class=\"failure\">{html.escape(message)}"
            f"{html.escape(chr(10) + trace) if trace else ''}</pre>"
        )
    return f"""
    <article>
      <header>
        <span class="status {status}">{status}</span>
        <h2>{name}</h2>
        <p class="meta">{suite}{(' · ' + tag) if tag else ''} · {fmt_duration(duration_seconds(result))} · {started}</p>
      </header>
      {param_html}
      {failure}
      {render_steps(result.get("steps") or [])}
      {render_attachments(result.get("attachments") or [])}
    </article>
    """


def build() -> str:
    results = latest_results()
    if not results:
        raise SystemExit(f"No Allure results in {RESULTS}")
    counts: dict[str, int] = {}
    total_seconds = 0.0
    for result in results:
        status = result.get("status") or "unknown"
        counts[status] = counts.get(status, 0) + 1
        total_seconds += duration_seconds(result)
    summary = " · ".join(f"{count} {status}" for status, count in sorted(counts.items()))
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    body = "\n".join(render_result(result) for result in results)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>eBay Playwright run report</title>
  <style>
    :root {{ color-scheme: light; }}
    body {{ margin: 0; font: 15px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f4f5f7; color: #1c1e21; }}
    main {{ max-width: 980px; margin: 0 auto; padding: 32px 20px 64px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    .summary {{ color: #4b5160; margin-bottom: 24px; }}
    article {{ background: #fff; border: 1px solid #e2e5ea; border-radius: 10px; padding: 16px 18px; margin: 0 0 16px; }}
    article h2 {{ font-size: 16px; margin: 8px 0 4px; }}
    .meta {{ margin: 0 0 12px; color: #5c6370; font-size: 13px; }}
    .status {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; font-weight: 650; text-transform: uppercase; letter-spacing: .03em; }}
    .passed {{ background: #e5f6ea; color: #0d7a32; }}
    .failed, .broken {{ background: #fde8e8; color: #b42318; }}
    .skipped, .unknown {{ background: #eee; color: #555; }}
    table {{ border-collapse: collapse; width: 100%; margin: 8px 0 12px; font-size: 13px; }}
    th, td {{ text-align: left; vertical-align: top; border-top: 1px solid #eceff3; padding: 6px 8px; }}
    th {{ width: 140px; color: #5c6370; font-weight: 600; }}
    pre {{ white-space: pre-wrap; word-break: break-word; background: #f7f8fa; border-radius: 8px; padding: 10px 12px; font-size: 12px; }}
    pre.failure {{ background: #fff4f4; }}
    ol.steps {{ margin: 8px 0 0; padding-left: 18px; }}
    ol.steps li {{ margin: 8px 0; }}
    figure {{ margin: 10px 0; }}
    figcaption {{ font-size: 12px; color: #5c6370; margin-bottom: 6px; }}
    img {{ max-width: 100%; height: auto; border: 1px solid #e2e5ea; border-radius: 8px; }}
    details {{ margin: 8px 0; }}
    summary {{ cursor: pointer; color: #244; }}
  </style>
</head>
<body>
  <main>
    <h1>eBay Playwright run report</h1>
    <p class="summary">{len(results)} tests · {summary} · {fmt_duration(total_seconds)} · generated {html.escape(generated)}</p>
    <p class="summary">Newest Allure result for each test. Raw <code>allure-results/</code> and <code>allure-report/</code> are not part of this file.</p>
    {body}
  </main>
</body>
</html>
"""


def main() -> None:
    OUTPUT.write_text(build(), encoding="utf-8")
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size / 1_000_000:.1f} MB)")


if __name__ == "__main__":
    main()
