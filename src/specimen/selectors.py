"""Registered feature-selection protocols (Phase 3).

The staining step library derives features (data side); selection narrows
them for a run (model side) — and that side must respect I1: a selector
**fits on the train segment only**, and the kept subset is applied unchanged
to valid/test. Registry idiom, same as ``assay.PROTOCOLS``: a new selection
shape joins as an entry, never as a fork.

Determinism: every selector is a pure function of (train data, seed, params).
Mutual information carries ``random_state=seed``; RFE's estimator is seeded;
ties break by (score desc, feature name) so equal scores cannot reorder.
This module is the ``[ml]`` blade — the zero-dependency core never imports it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from .staining import require_registered  # noqa: F401  (shared refusal idiom)


@dataclass(frozen=True)
class Selection:
    """What a selector returns: the kept features plus its recorded params."""

    features: tuple[str, ...]
    params: tuple[tuple[str, float], ...]


SelectorFn = Callable[
    [list[list[float]], list[int], tuple[str, ...], int, Mapping[str, float]],
    Selection,
]
SELECTORS: dict[str, SelectorFn] = {}


def _registered(name: str) -> Callable[[SelectorFn], SelectorFn]:
    """Register under the protocol-style kebab-case name the CLI and records use."""

    def wrap(fn: SelectorFn) -> SelectorFn:
        SELECTORS[name] = fn
        return fn

    return wrap


def _top_k(scored: list[tuple[float, str]], k: int) -> tuple[str, ...]:
    """Deterministic top-k: score descending, ties by feature name."""
    ranked = sorted(scored, key=lambda pair: (-pair[0], pair[1]))
    return tuple(name for _, name in ranked[:k])


@_registered("correlation-filter")
def correlation_filter(
    x_train: list[list[float]],
    y_train: list[int],
    features: tuple[str, ...],
    seed: int,
    params: Mapping[str, float],
) -> Selection:
    """Keep features whose |Pearson r| with the target is >= ``threshold``.

    Train rows only (I1). A feature with zero variance scores 0 and drops.
    """
    threshold = params["threshold"]
    n = len(y_train)
    mean_y = sum(y_train) / n
    kept: list[tuple[float, str]] = []
    for index, name in enumerate(features):
        column = [row[index] for row in x_train]
        mean_x = sum(column) / n
        cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(column, y_train, strict=True))
        var_x = sum((x - mean_x) ** 2 for x in column)
        var_y = sum((y - mean_y) ** 2 for y in y_train)
        r = cov / (var_x**0.5 * var_y**0.5) if var_x > 0 and var_y > 0 else 0.0
        if abs(r) >= threshold:
            kept.append((abs(r), name))
    return Selection(features=_top_k(kept, len(kept)), params=(("threshold", threshold),))


@_registered("mutual-information-top-k")
def mutual_information_top_k(
    x_train: list[list[float]],
    y_train: list[int],
    features: tuple[str, ...],
    seed: int,
    params: Mapping[str, float],
) -> Selection:
    """Keep the ``k`` features with the highest train-segment mutual information
    with the target (``random_state=seed``)."""
    from sklearn.feature_selection import mutual_info_classif

    k = int(params["k"])
    scores = mutual_info_classif(x_train, y_train, random_state=seed)
    scored = [(float(score), name) for score, name in zip(scores, features, strict=True)]
    kept = _top_k(scored, min(k, len(features)))
    return Selection(features=kept, params=(("k", float(k)),))


@_registered("rfe-top-k")
def rfe_top_k(
    x_train: list[list[float]],
    y_train: list[int],
    features: tuple[str, ...],
    seed: int,
    params: Mapping[str, float],
) -> Selection:
    """Recursive feature elimination down to ``k`` features, with a seeded
    logistic estimator. Unscaled: RFE ranks by the estimator's coefficients,
    and the model pipeline scales separately when the assay trains."""
    from sklearn.feature_selection import RFE
    from sklearn.linear_model import LogisticRegression

    k = int(params["k"])
    estimator = LogisticRegression(max_iter=1000, random_state=seed)
    selector = RFE(estimator, n_features_to_select=min(k, len(features)))
    selector.fit(x_train, y_train)
    kept = tuple(name for name, flag in zip(features, selector.support_, strict=True) if flag)
    return Selection(features=kept, params=(("k", float(k)),))


def run_selector(
    name: str,
    x_train: list[list[float]],
    y_train: list[int],
    features: tuple[str, ...],
    seed: int,
    params: Mapping[str, float],
) -> Selection:
    """Registry dispatch; an unknown selector is a refusal, not a fallback."""
    runner = SELECTORS.get(name)
    if runner is None:
        raise ValueError(f"unknown selector {name!r} (registered: {sorted(SELECTORS)})")
    return runner(x_train, y_train, features, seed, params)


__all__ = ["SELECTORS", "Selection", "correlation_filter", "mutual_information_top_k", "rfe_top_k", "run_selector"]
