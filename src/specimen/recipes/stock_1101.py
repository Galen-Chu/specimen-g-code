"""First real specimen: 1101.TW (台泥) daily prices from TWSE open data.

Raw is the verbatim monthly ``rwd/zh/afterTrading/STOCK_DAY`` JSON fetched
by ``scripts/acquire_1101.py`` (ROC-era dates, comma-grouped numbers,
``--`` on no-trade days). Every cleaning rule is declared here and recorded
in the manifest steps - none is implicit:

- parse_months: months whose ``stat`` is not "OK" are skipped.
- normalize_roc_dates: "115/09/01" -> "2026-09-01" (ROC + 1911).
- strip_thousands: comma grouping removed ("108,834,320" -> "108834320").
- drop_incomplete: no-trade days (any of OHLC/volume/value/transactions
  marked ``--`` or empty) are incomplete and dropped - values pass through
  as-served strings otherwise; no reformatting.
- dedupe_keep_last: duplicate (date, symbol) keeps the last occurrence.
- sort_by_key: rows sorted by (date, symbol).
- label_forward_return_90d: label = 1 iff the as-of close 90 calendar days
  later is at least 10% above today's close (as-of = last close at or
  before date+90d, drawn from this table's own series). Rows without a
  full 90-day lookahead are dropped - they cannot be labeled honestly.

Splits (time-ordered, registered in the manifest): train through
2025-12-31 (both classes present: the 2025H2 advance supplies positives),
valid 2026-01-01..2026-06-30, test 2026-07-01 onward - the most recent
fully-labelable window, which also carries both classes. The seed is
recorded for protocol-level reproducibility; this recipe is deterministic
and seed-independent.
"""

from __future__ import annotations

import csv
import io
import json
from bisect import bisect_right
from collections.abc import Mapping
from datetime import date, timedelta

from ..manifest import ColumnSpec, Splits, TableContract

STEPS = (
    "parse_months",
    "normalize_roc_dates",
    "strip_thousands",
    "drop_incomplete",
    "dedupe_keep_last",
    "sort_by_key",
    "label_forward_return_90d",
)
INPUTS = tuple(
    f"twse_stock_day_{year}{month:02d}.json"
    for year in range(2024, 2027)
    for month in range(1, 13)
    if f"{year}{month:02d}" <= "202610"
)
CONTRACTS = (
    TableContract(
        name="daily",
        grain="daily",
        key=("date", "symbol"),
        columns=(
            ColumnSpec("date", "date"),
            ColumnSpec("symbol", "string"),
            ColumnSpec("open", "float", lo=0.0, availability_lag_days=0.0),
            ColumnSpec("high", "float", lo=0.0, availability_lag_days=0.0),
            ColumnSpec("low", "float", lo=0.0, availability_lag_days=0.0),
            ColumnSpec("close", "float", lo=0.0, availability_lag_days=0.0),
            ColumnSpec("volume", "int", lo=0.0, availability_lag_days=0.0),
            ColumnSpec("value", "int", lo=0.0, availability_lag_days=0.0),
            ColumnSpec("transactions", "int", lo=0.0, availability_lag_days=0.0),
            ColumnSpec("label", "int", lo=0.0, hi=1.0, availability_lag_days=90.0),
        ),
    ),
)
SPLITS = Splits(method="time-ordered", train_end="2025-12-31", valid_end="2026-06-30")

FIELDS = (1, 2, 3, 4, 5, 6, 8)  # volume, value, open, high, low, close, transactions
HEADER = ("date", "symbol", "open", "high", "low", "close", "volume", "value", "transactions", "label")
FORWARD_DAYS = 90
THRESHOLD = 0.10


def _iso(roc: str) -> str:
    year, month, day = roc.split("/")
    return f"{int(year) + 1911:04d}-{int(month):02d}-{int(day):02d}"


def run(seed: int, inputs: Mapping[str, bytes]) -> dict[str, str]:
    rows: list[dict[str, str]] = []
    for name in INPUTS:  # parse_months: INPUTS order is chronological
        month = json.loads(inputs[name])
        if month.get("stat") != "OK":
            continue
        for raw in month["data"]:
            values = [raw[i].replace(",", "") for i in FIELDS]  # strip_thousands
            if any(value == "" or value == "--" for value in values):
                continue  # drop_incomplete: no-trade days carry "--"
            rows.append(
                {
                    "date": _iso(raw[0]),  # normalize_roc_dates
                    "symbol": "1101",
                    "open": values[2],
                    "high": values[3],
                    "low": values[4],
                    "close": values[5],
                    "volume": values[0],
                    "value": values[1],
                    "transactions": values[6],
                }
            )

    by_key: dict[tuple[str, str], dict[str, str]] = {}  # dedupe_keep_last
    for row in rows:
        by_key[(row["date"], row["symbol"])] = row
    sorted_rows = sorted(by_key.values(), key=lambda r: (r["date"], r["symbol"]))  # sort_by_key

    dates = [row["date"] for row in sorted_rows]
    closes = [float(row["close"]) for row in sorted_rows]
    last_day = date.fromisoformat(dates[-1])

    labeled: list[dict[str, str]] = []  # label_forward_return_90d
    for row, today, close in zip(sorted_rows, dates, closes, strict=True):
        horizon = date.fromisoformat(today) + timedelta(days=FORWARD_DAYS)
        if horizon > last_day:
            continue  # no full 90-day lookahead: dropped, not guessed
        future = closes[bisect_right(dates, horizon.isoformat()) - 1]  # as-of close
        label = 1 if future / close - 1.0 >= THRESHOLD else 0
        labeled.append({**row, "label": str(label)})

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=HEADER, lineterminator="\n")
    writer.writeheader()
    for row in labeled:
        writer.writerow({name: row[name] for name in HEADER})
    return {"daily": buffer.getvalue()}
