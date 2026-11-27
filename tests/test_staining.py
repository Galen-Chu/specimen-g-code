"""Staining step library: named steps, availability-respecting as-of, refusals."""

from __future__ import annotations

import pytest

from specimen.staining import STEPS, asof_join, diff, pct_change, ratio, require_registered, step_call

QUARTERLY = (
    "date,symbol,revenue,net_income,total_assets\n"
    "2025-09-30,1101,41000000,-10200000,600000000\n"
    "2025-12-31,1101,42000000,3000000,605000000\n"
    "2026-03-31,1101,43000000,5000000,610000000\n"
)
DAILY = (
    "date,symbol,close,volume,label\n"
    "2025-10-15,1101,50.0,1000,0\n"  # before any availability: dropped
    "2025-12-29,1101,52.0,1100,1\n"  # first usable day (2025-09-30 + 90d)
    "2026-01-05,1101,53.0,1200,0\n"  # still the 2025Q3 report
    "2026-04-15,1101,55.0,1300,1\n"  # 2025Q4 + 90d = 2026-03-31 → the new report
)


class TestAsofJoin:
    def test_values_follow_the_disclosure_lag(self) -> None:
        out = asof_join(QUARTERLY, DAILY, columns=("revenue", "net_income"), lag_days=90.0)
        rows = out.strip().split("\n")
        assert rows[0].endswith(",revenue,net_income")
        by_date = {row.split(",")[0]: row for row in rows[1:]}
        # 2025-10-15 dropped: no report was public yet — never filled.
        assert "2025-10-15" not in by_date
        # 2025-12-29..2026-03-30 use the 2025Q3 statement (usable from 2025-12-29).
        assert by_date["2025-12-29"].endswith("41000000,-10200000")
        assert by_date["2026-01-05"].endswith("41000000,-10200000")
        # From 2026-03-31 the 2025Q4 statement is public.
        assert by_date["2026-04-15"].endswith("42000000,3000000")

    def test_lag_below_ninety_refuses(self) -> None:
        with pytest.raises(ValueError, match=">= 90"):
            asof_join(QUARTERLY, DAILY, columns=("revenue",), lag_days=45.0)

    def test_unknown_source_column_refuses(self) -> None:
        with pytest.raises(ValueError, match="not in the source header"):
            asof_join(QUARTERLY, DAILY, columns=("dividend",), lag_days=90.0)

    def test_deterministic(self) -> None:
        assert asof_join(QUARTERLY, DAILY, columns=("revenue",), lag_days=90.0) == asof_join(
            QUARTERLY, DAILY, columns=("revenue",), lag_days=90.0
        )


class TestArithmetic:
    TABLE = "date,symbol,revenue,net_income\n2026-03-31,1101,43000000,5000000\n2026-06-30,1101,40000000,4000000\n"

    def test_ratio(self) -> None:
        out = ratio(self.TABLE, numerator="net_income", denominator="revenue", name="net_margin")
        rows = out.strip().split("\n")
        assert rows[0].endswith(",net_margin")
        assert rows[1].endswith(repr(5000000 / 43000000))
        assert rows[2].endswith(repr(4000000 / 40000000))

    def test_ratio_zero_denominator_refuses(self) -> None:
        with pytest.raises(ValueError, match="zero denominator"):
            ratio("date,symbol,revenue\n2026-03-31,1101,0\n", numerator="revenue", denominator="revenue", name="x")

    def test_ratio_existing_name_refuses(self) -> None:
        with pytest.raises(ValueError, match="already exists"):
            ratio(self.TABLE, numerator="net_income", denominator="revenue", name="revenue")

    def test_diff(self) -> None:
        out = diff(self.TABLE, a="revenue", b="net_income", name="gross_proxy")
        rows = out.strip().split("\n")
        assert rows[1].endswith("38000000")

    def test_pct_change_drops_lookback_rows(self) -> None:
        daily = "date,symbol,close\n2026-01-01,X,100.0\n2026-01-02,X,110.0\n2026-01-03,X,99.0\n"
        out = pct_change(daily, column="close", periods=2, name="mom")
        rows = out.strip().split("\n")
        assert len(rows) == 2  # header + one row: the first two lack the lookback
        assert rows[1].endswith(repr(99.0 / 100.0 - 1.0))

    def test_pct_change_periods_below_one_refuses(self) -> None:
        with pytest.raises(ValueError, match="periods must be >= 1"):
            pct_change("date,symbol,close\n2026-01-01,X,100.0\n", column="close", periods=0, name="x")


class TestRegistry:
    def test_step_call_is_canonical_and_sorted(self) -> None:
        record = step_call("asof_join", lag_days=90.0, columns=("revenue", "net_income"), source="quarterly")
        assert record == "asof_join(columns=revenue,net_income, lag_days=90, source=quarterly)"

    def test_step_call_refuses_unregistered_names(self) -> None:
        with pytest.raises(ValueError, match="unknown staining step"):
            step_call("magic", x=1)

    def test_require_registered(self) -> None:
        require_registered("asof_join")
        with pytest.raises(ValueError, match="unknown staining step"):
            require_registered("magic")

    def test_registry_covers_the_library(self) -> None:
        assert {"asof_join", "diff", "ratio", "pct_change"} <= set(STEPS)
