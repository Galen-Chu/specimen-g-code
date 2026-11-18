"""Assay: comparable training protocols on sealed specimens.

Refuse, don't warn. Entry order: I2 target purity, contract conformance,
numeric-feature and label checks, then the split — obtained only through
``read_split`` against the sealed boundaries (self-cutting experiments
have nothing to cut on). A run appends its records to the specimen's
manifest; ``[[assays]]`` is append-only evidence and never a reproduction
input — the reproduction surface stays (raw hash + recipe + seed).

This module is the ``[ml]`` blade: it needs scikit-learn, and the
zero-dependency core never imports it. Metrics are annotations of a run:
deterministic within an environment, informative across environments.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, NoReturn

from .catalog import load
from .contract import validate_table
from .hashing import sha256_bytes
from .invariants import check_target_purity, check_time_safety, read_split
from .manifest import AssayRecord, Manifest, write_manifest

PROTOCOL = "time-split-baseline"
NUMERIC_TYPES = frozenset({"float", "int"})


@dataclass(frozen=True)
class ModelSpec:
    """A baseline model: a factory bound to its declared hyperparameters."""

    name: str
    factory: Callable[[], Any]
    hyperparams: tuple[tuple[str, float], ...]


def _model_specs(seed: int, train_size: int) -> list[ModelSpec]:
    from sklearn.dummy import DummyClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.tree import DecisionTreeClassifier

    neighbors = min(5, train_size)
    return [
        ModelSpec("constant", lambda: DummyClassifier(strategy="prior"), ()),
        ModelSpec(
            "logistic",
            lambda: LogisticRegression(C=1.0, max_iter=1000, random_state=seed),
            (("C", 1.0), ("max_iter", 1000.0)),
        ),
        ModelSpec(
            "decision_tree", lambda: DecisionTreeClassifier(max_depth=3, random_state=seed), (("max_depth", 3.0),)
        ),
        ModelSpec("knn", lambda: KNeighborsClassifier(n_neighbors=neighbors), (("n_neighbors", float(neighbors)),)),
    ]


def _refuse(problems: Sequence[str]) -> NoReturn:
    raise ValueError("; ".join(problems))


def _date_column(manifest: Manifest, table: str) -> str:
    contract = manifest.contract_of[table]
    for key in contract.key:
        column = contract.column(key)
        if column is not None and column.type == "date":
            return key
    _refuse([f"contract {table!r}: no key column of type 'date' to split on"])


def run_assay(
    specimen_dir: str | Path,
    table: str,
    target: str,
    features: Sequence[str],
    seed: int = 0,
    protocol: str = PROTOCOL,
) -> list[AssayRecord]:
    """Run the baseline comparison on a sealed specimen; returns the appended records.

    Gates first (I2 purity, contract conformance, numeric features, binary
    target, I1 split safety), then fit on train and score on test. The
    manifest on disk gains one ``[[assays]]`` record per model, appended.
    """
    if protocol != PROTOCOL:
        _refuse([f"unknown protocol {protocol!r} (available: {PROTOCOL!r})"])
    directory = Path(specimen_dir)
    manifest = load(directory)
    if table not in manifest.contract_of:
        _refuse([f"table {table!r} is not declared in the manifest"])
    contract = manifest.contract_of[table]

    purity = check_target_purity(contract, target, features)
    if purity:
        _refuse(purity)

    output = next((o for o in manifest.outputs if o.name == table), None)
    if output is None:
        _refuse([f"table {table!r} has no output file in the manifest"])
    if sha256_bytes((directory / output.file).read_bytes()) != output.sha256:
        _refuse([f"{output.file} hash mismatch - the specimen is not intact; run verify"])
    text = (directory / output.file).read_text(encoding="utf-8")

    conformance = validate_table(contract, text)
    if conformance:
        _refuse(conformance)

    non_numeric = [f for f in features if (c := contract.column(f)) is not None and c.type not in NUMERIC_TYPES]
    if non_numeric:
        _refuse([f"features must be numeric (float/int), got {non_numeric}"])

    assignment = read_split(text, _date_column(manifest, table), manifest.splits)
    safety = check_time_safety(assignment, manifest.splits)
    if safety:
        _refuse(safety)

    rows = list(csv.DictReader(io.StringIO(text)))
    labels = [row[target] for row in rows]
    bad_labels = sorted({value for value in labels if value not in ("0", "1")})
    if bad_labels:
        _refuse([f"target {target!r} must be binary (0/1), got {bad_labels}"])

    y_train = [int(labels[i]) for i in assignment.train]
    x_train = [[float(rows[i][f]) for f in features] for i in assignment.train]
    if len(set(y_train)) < 2:
        _refuse(["train segment has a single class - nothing to learn from"])
    y_test = [int(labels[i]) for i in assignment.test]
    x_test = [[float(rows[i][f]) for f in features] for i in assignment.test]

    records = []
    for spec in _model_specs(seed, len(y_train)):
        model = spec.factory()
        model.fit(x_train, y_train)
        metrics: list[tuple[str, float]] = []
        if len(set(y_test)) == 2:
            probability = model.predict_proba(x_test)[:, 1]
            metrics.append(("roc_auc", _roc_auc(y_test, probability)))
            metrics.append(("pr_auc", _pr_auc(y_test, probability)))
        else:
            metrics = [("roc_auc", float("nan")), ("pr_auc", float("nan"))]
        records.append(
            AssayRecord(
                protocol=protocol,
                model=spec.name,
                seed=seed,
                train_end=manifest.splits.train_end,
                valid_end=manifest.splits.valid_end,
                hyperparams=spec.hyperparams,
                metrics=tuple(sorted(metrics)),
            )
        )

    appended = replace(manifest, assays=manifest.assays + tuple(records))
    write_manifest(appended, directory / "manifest.toml")
    return records


def _roc_auc(y_true: list[int], probability: Any) -> float:
    from sklearn.metrics import roc_auc_score

    return float(roc_auc_score(y_true, probability))


def _pr_auc(y_true: list[int], probability: Any) -> float:
    from sklearn.metrics import average_precision_score

    return float(average_precision_score(y_true, probability))


__all__ = ["PROTOCOL", "ModelSpec", "run_assay"]
