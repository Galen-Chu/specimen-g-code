"""Feature-selection protocols: train-scoped (I1), deterministic, registry-gated."""

from __future__ import annotations

import pytest

pytest.importorskip("sklearn", reason="the selection blade needs the [ml] extra")

from specimen.selectors import SELECTORS, correlation_filter, run_selector  # noqa: E402

# Ten train rows, three features: informative (the label IS its threshold),
# noisy (weakly uncorrelated), dead (constant — no variance, no information).
FEATURES = ("informative", "noisy", "dead")
X_TRAIN = [
    [1.0, 3.0, 5.0],
    [2.0, 1.0, 5.0],
    [3.0, 4.0, 5.0],
    [4.0, 2.0, 5.0],
    [5.0, 3.0, 5.0],
    [6.0, 1.0, 5.0],
    [7.0, 4.0, 5.0],
    [8.0, 2.0, 5.0],
    [9.0, 3.0, 5.0],
    [10.0, 1.0, 5.0],
]
Y_TRAIN = [0, 0, 0, 0, 0, 1, 1, 1, 1, 1]  # label = informative >= 6


def test_registry_has_the_three_protocols() -> None:
    assert {"correlation-filter", "mutual-information-top-k", "rfe-top-k"} <= set(SELECTORS)


def test_unknown_selector_refuses() -> None:
    with pytest.raises(ValueError, match="unknown selector"):
        run_selector("astrology", X_TRAIN, Y_TRAIN, FEATURES, 0, {})


def test_correlation_filter_keeps_the_informative_feature() -> None:
    selection = correlation_filter(X_TRAIN, Y_TRAIN, FEATURES, 0, {"threshold": 0.3})
    assert selection.features == ("informative",)
    assert selection.params == (("threshold", 0.3),)


def test_correlation_filter_deterministic_per_seed() -> None:
    one = correlation_filter(X_TRAIN, Y_TRAIN, FEATURES, 0, {"threshold": 0.1})
    two = correlation_filter(X_TRAIN, Y_TRAIN, FEATURES, 0, {"threshold": 0.1})
    assert one == two


def test_mutual_information_top_k() -> None:
    selection = run_selector("mutual-information-top-k", X_TRAIN, Y_TRAIN, FEATURES, 7, {"k": 2.0})
    assert len(selection.features) == 2
    assert "informative" in selection.features  # the perfect dependency must survive
    assert selection.params == (("k", 2.0),)


def test_rfe_top_k() -> None:
    selection = run_selector("rfe-top-k", X_TRAIN, Y_TRAIN, FEATURES, 3, {"k": 1.0})
    assert selection.features == ("informative",)
    assert selection.params == (("k", 1.0),)
