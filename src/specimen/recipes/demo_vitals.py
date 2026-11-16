"""Demo recipe: the Phase 1 proof of machinery (docs/CASE-STUDY in miniature).

Takes one messy raw CSV — mixed grains, duplicated keys, timestamp-suffixed
dates, empty cells — and applies the four registered transforms every
specimen recipe is named after: normalize_dates, split_grains,
dedupe_keep_last, sort_by_key. Declared cleaning rules: quarterly rows are
those carrying a note; daily rows missing their close are incomplete and
dropped; duplicate (date, symbol) keys keep the last occurrence. The
outputs are two single-grain tables (``daily``, ``quarterly``) that satisfy
their contracts. Everything is stdlib and seed-independent (the seed is
recorded for protocol-level reproducibility; Phase 2 recipes will sample
with it).
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping

from ..manifest import ColumnSpec, Splits, TableContract

STEPS = ("normalize_dates", "split_grains", "dedupe_keep_last", "sort_by_key")
INPUTS = ("vitals_raw.csv",)
CONTRACTS = (
    TableContract(
        name="daily",
        grain="daily",
        key=("date", "symbol"),
        columns=(
            ColumnSpec("close", "float", lo=0.0, hi=1000.0),
            ColumnSpec("date", "date"),
            ColumnSpec("symbol", "string"),
            ColumnSpec("volume", "int", lo=0.0),
        ),
    ),
    TableContract(
        name="quarterly",
        grain="quarterly",
        key=("date", "symbol"),
        columns=(
            ColumnSpec("date", "date"),
            ColumnSpec("note", "string"),
            ColumnSpec("symbol", "string"),
        ),
    ),
)
SPLITS = Splits(method="time-ordered", train_end="2026-01-10", valid_end="2026-01-20")


def run(seed: int, inputs: Mapping[str, bytes]) -> dict[str, str]:
    raw_rows = list(csv.DictReader(io.StringIO(inputs["vitals_raw.csv"].decode("utf-8"))))

    rows = [dict(r) for r in raw_rows]
    for r in rows:  # normalize_dates: "2026-01-02 00:00:00" -> "2026-01-02"
        r["date"] = r["date"].split(" ")[0].strip()

    # split_grains: rows carrying a note are quarterly; rows missing both close
    # and note are incomplete daily rows and are dropped (a declared rule, not
    # a silent one - see the module docstring).
    quarterly_rows = [r for r in rows if r["note"] != ""]
    daily_rows = [r for r in rows if r["note"] == "" and r["close"] != ""]

    by_key: dict[tuple[str, str], dict[str, str]] = {}  # dedupe_keep_last
    for r in daily_rows:
        by_key[(r["date"], r["symbol"])] = r
    daily = sorted(by_key.values(), key=lambda r: (r["date"], r["symbol"]))  # sort_by_key
    quarterly = sorted(quarterly_rows, key=lambda r: (r["date"], r["symbol"]))

    daily_text = _to_csv(("date", "symbol", "close", "volume"), daily)
    quarterly_text = _to_csv(("date", "symbol", "note"), quarterly)
    return {"daily": daily_text, "quarterly": quarterly_text}


def _to_csv(header: tuple[str, ...], rows: list[dict[str, str]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=header, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row[k] for k in header})
    return buffer.getvalue()
