"""Acquisition: re-crawl 1101.TW raw material from Taiwan open data.

Daily: the rwd/zh/afterTrading/STOCK_DAY JSON, fetched per month, stored
verbatim under data/raw/1101/. Quarterly: the MOPS t187apXX datasets, which
migrated to openapi.twse.com.tw/v1/opendata/ as JSON — snapshot endpoints
(no period parameters; always the latest quarter), fetched under
data/raw/1101/quarterly/ and accumulated forward, one immutable file per
(ROC year, quarter). Historical quarterly statements (2025Q3..2026Q3) are
backfilled from Yahoo Finance via yfinance — a declared third-party source;
the overlap quarter cross-validates it against the official snapshot
(yf Q1-Q3 quarterly sum x1000 == official YTD in TWD thousands, exact).

Acquisition never transforms; the recipe owns every transformation
(ROC-era dates, comma grouping, unit harmonization are all downstream
steps, so raw stays exactly as served).

Usage:
  python scripts/acquire_1101.py                      # daily, 202401..202610
  python scripts/acquire_1101.py 202401 202610        # daily, explicit range
  python scripts/acquire_1101.py --quarterly          # official quarterly snapshots
  python scripts/acquire_1101.py --backfill-yfinance  # yfinance quarterly backfill (needs yfinance)
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

STOCK_NO = "1101"
URL = "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?date={ym}01&stockNo={stock}&response=json"
USER_AGENT = "specimen-g-code/0.2.0 (+https://github.com/Galen-Chu/specimen-g-code)"
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "1101"
QUARTERLY_DIR = OUT_DIR / "quarterly"
QUARTERLY_URLS = {
    "06": "https://openapi.twse.com.tw/v1/opendata/t187ap06_L_ci",  # income statement (general industry)
    "07": "https://openapi.twse.com.tw/v1/opendata/t187ap07_L_ci",  # balance sheet (general industry)
}


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def fetch_quarterly() -> None:
    """Official snapshots: one immutable file per (ROC year, quarter), accumulated forward."""
    QUARTERLY_DIR.mkdir(parents=True, exist_ok=True)
    for code, url in QUARTERLY_URLS.items():
        payload = fetch(url)
        sample = next((r for r in json.loads(payload) if r.get("公司代號") == STOCK_NO), None)
        if sample is None:
            print(f"quarterly t187ap{code}: no {STOCK_NO} row; nothing saved")
            continue
        name = f"t187ap{code}_L_ci_{sample['年度']}Q{int(sample['季別'])}.json"
        target = QUARTERLY_DIR / name
        if target.exists():
            print(f"quarterly t187ap{code}: {name} already sealed - snapshots never overwrite")
            continue
        target.write_bytes(payload)
        print(f"quarterly t187ap{code}: saved {name}")


def backfill_yfinance() -> None:
    """Historical quarterly statements from Yahoo Finance (declared third-party)."""
    import yfinance as yf

    QUARTERLY_DIR.mkdir(parents=True, exist_ok=True)
    for kind, attr in (("income", "quarterly_income_stmt"), ("balance", "quarterly_balance_sheet")):
        frame = getattr(yf.Ticker(f"{STOCK_NO}.TW"), attr)
        frame.columns = [column.strftime("%Y-%m-%d") for column in frame.columns]
        target = QUARTERLY_DIR / f"yf_{STOCK_NO}_quarterly_{kind}.csv"
        frame.to_csv(target, lineterminator="\n")
        print(f"yfinance {kind}: {frame.shape[1]} quarters -> {target.name}")


def months(start: str, end: str) -> list[str]:
    year, month = int(start[:4]), int(start[4:])
    out = []
    while True:
        ym = f"{year}{month:02d}"
        if ym > end:
            return out
        out.append(ym)
        month += 1
        if month == 13:
            year, month = year + 1, 1


def main(argv: list[str]) -> int:
    if "--quarterly" in argv:
        fetch_quarterly()
        return 0
    if "--backfill-yfinance" in argv:
        backfill_yfinance()
        return 0
    start = argv[1] if len(argv) > 1 else "202401"
    end = argv[2] if len(argv) > 2 else "202610"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    landed = 0
    skipped: list[str] = []
    for ym in months(start, end):
        target = OUT_DIR / f"twse_stock_day_{ym}.json"
        if target.exists():
            landed += 1
            continue
        payload = fetch(URL.format(ym=ym, stock=STOCK_NO))
        try:
            stat = json.loads(payload).get("stat")
        except (json.JSONDecodeError, UnicodeDecodeError):
            stat = None
        if stat != "OK":
            skipped.append(ym)
            continue
        target.write_bytes(payload)  # verbatim - acquisition never transforms
        landed += 1
        time.sleep(0.6)  # be polite to the source
    print(f"acquisition: {landed} months under {OUT_DIR}; skipped (no data): {skipped or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
