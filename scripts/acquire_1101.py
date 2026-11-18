"""Acquisition: re-crawl 1101.TW raw material from Taiwan Stock Exchange open data.

The daily trading JSON (rwd/zh/afterTrading/STOCK_DAY) is fetched per month
and stored verbatim under data/raw/1101/ — acquisition never transforms;
the recipe owns every transformation (ROC-era dates and comma-grouped
numbers are normalized downstream, so the raw stays exactly as served).

Quarterly financials (MOPS opendata) are not fetched here: that host was
unresolvable from the authoring machine (2026-11-18); extend this script
when the endpoint is reachable.

Usage: python scripts/acquire_1101.py [start_yyyymm end_yyyymm]
       e.g. python scripts/acquire_1101.py 202401 202610
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


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


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
