from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config.settings import ROOT_DIR


def load_test_scenarios(path: Path | None = None) -> list[dict[str, Any]]:
    data_path = path or (ROOT_DIR / "data" / "test_data.json")
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    scenarios = payload.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError(f"No scenarios found in {data_path}")
    return scenarios
