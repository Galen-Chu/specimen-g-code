"""Assay: comparable training protocols on sealed specimens (docs/SOP.md section 5).

Refuse, don't warn. ``run_assay`` runs the domain-independent gates first —
protocol lookup, table lookup, I2 target purity, I3 grain separation,
output-hash integrity — then hands an ``AssayContext`` to the registered
protocol. The split comes only through ``read_split`` against the sealed
boundaries (self-cutting experiments have nothing to cut on). A run
appends its records to the specimen's manifest; ``[[assays]]`` is
append-only evidence and never a reproduction input — the reproduction
surface stays (raw hash + recipe + seed).

Protocols are a registry (``PROTOCOLS``): a new evaluation shape joins as
a new entry, never as a fork of the SOP. This module is the ``[ml]``
blade: it needs scikit-learn, and the zero-dependency core never imports
it. Metrics are annotations of a run: deterministic within an
environment, informative across environments.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, NoReturn

from .catalog import load
from .contract import validate_table
from .hashing import sha256_bytes
from .invariants import check_grain_separation, check_target_purity, check_time_safety, read_split
from .manifest import AssayRecord, Manifest, TableContract, write_manifest

PROTOCOL = "time-split-baseline"
NUMERIC_TYPES = frozenset({"float", "int"})


@dataclass(frozen=True)
class ModelSpec:
    """A baseline model: a factory bound to its declared hyperparameters."""

    name: str
    factory: Callable[[], Any]
    hyperparams: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class AssayContext:
    """What a protocol receives once the domain-independent gates have passed."""

    directory: Path
    manifest: Manifest
    contract: TableContract
    table_text: str
    target: str
    features: tuple[str, ...]
    seed: int


ProtocolFn = Callable[[AssayContext], list[AssayRecord]]
PROTOCOLS: dict[str, ProtocolFn] = {}  # the registry every new protocol joins


def _model_specs(seed: int, train_size: int) -> list[ModelSpec]:
    """Baselines. Scale-sensitive models (logistic, knn) standardize inside a
    pipeline, so the scaler fits on the train segment only - invariant I1 says
    transformers fit on train, never on the full data. The ``scaled`` entry in
    their recorded hyperparams marks the standardization as part of the model."""
    from sklearn.dummy import DummyClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.tree import DecisionTreeClassifier

    neighbors = min(5, train_size)
    return [
        ModelSpec("constant", lambda: DummyClassifier(strategy="prior"), ()),
        ModelSpec(
            "logistic",
            lambda: Pipeline(
                [("scale", StandardScaler()), ("model", LogisticRegression(C=1.0, max_iter=1000, random_state=seed))]
            ),
            (("C", 1.0), ("max_iter", 1000.0), ("scaled", 1.0)),
        ),
        ModelSpec(
            "decision_tree", lambda: DecisionTreeClassifier(max_depth=3, random_state=seed), (("max_depth", 3.0),)
        ),
        ModelSpec(
            "knn",
            lambda: Pipeline([("scale", StandardScaler()), ("model", KNeighborsClassifier(n_neighbors=neighbors))]),
            (("n_neighbors", float(neighbors)), ("scaled", 1.0)),
        ),
    ]


def _refuse(problems: Sequence[str]) -> NoReturn:
    raise ValueError("; ".join(problems))


def _date_column(contract: TableContract) -> str:
    for key in contract.key:
        column = contract.column(key)
        if column is not None and column.type == "date":
            return key
    _refuse([f"contract {contract.name!r}: no key column of type 'date' to split on"])


def _time_split_baseline(ctx: AssayContext) -> list[AssayRecord]:
    """Fit the baselines on the train segment, score on test, against the sealed split."""
    conformance = validate_table(ctx.contract, ctx.table_text)
    if conformance:
        _refuse(conformance)

    non_numeric = [f for f in ctx.features if (c := ctx.contract.column(f)) is not None and c.type not in NUMERIC_TYPES]
    if non_numeric:
        _refuse([f"features must be numeric (float/int), got {non_numeric}"])

    assignment = read_split(ctx.table_text, _date_column(ctx.contract), ctx.manifest.splits)
    safety = check_time_safety(assignment, ctx.manifest.splits)
    if safety:
        _refuse(safety)

    rows = list(csv.DictReader(io.StringIO(ctx.table_text)))
    labels = [row[ctx.target] for row in rows]
    bad_labels = sorted({value for value in labels if value not in ("0", "1")})
    if bad_labels:
        _refuse([f"target {ctx.target!r} must be binary (0/1), got {bad_labels}"])

    y_train = [int(labels[i]) for i in assignment.train]
    x_train = [[float(rows[i][f]) for f in ctx.features] for i in assignment.train]
    if len(set(y_train)) < 2:
        _refuse(["train segment has a single class - nothing to learn from"])
    y_test = [int(labels[i]) for i in assignment.test]
    x_test = [[float(rows[i][f]) for f in ctx.features] for i in assignment.test]

    records = []
    for spec in _model_specs(ctx.seed, len(y_train)):
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
                protocol=PROTOCOL,
                model=spec.name,
                seed=ctx.seed,
                train_end=ctx.manifest.splits.train_end,
                valid_end=ctx.manifest.splits.valid_end,
                hyperparams=spec.hyperparams,
                metrics=tuple(sorted(metrics)),
            )
        )
    return records


PROTOCOLS[PROTOCOL] = _time_split_baseline


def run_assay(
    specimen_dir: str | Path,
    table: str,
    target: str,
    features: Sequence[str],
    seed: int = 0,
    protocol: str = PROTOCOL,
    selector: str | None = None,
    selector_params: Mapping[str, float] | None = None,
) -> list[AssayRecord]:
    """Run a registered protocol on a sealed specimen; returns the appended records.

    Domain-independent gates first (protocol lookup, table lookup, I2
    purity, I3 grain separation, output-hash integrity), then the protocol
    runs behind its own checks. With ``selector`` set, the registered
    selection fits on the **train segment only** (I1) and the models see the
    narrowed feature list; the record names the selector, its params and the
    exact features the models saw. The manifest on disk gains one
    ``[[assays]]`` record per model, appended — never overwritten.
    """
    runner = PROTOCOLS.get(protocol)
    if runner is None:
        _refuse([f"unknown protocol {protocol!r} (available: {sorted(PROTOCOLS)})"])
    directory = Path(specimen_dir)
    manifest = load(directory)
    if table not in manifest.contract_of:
        _refuse([f"table {table!r} is not declared in the manifest"])
    contract = manifest.contract_of[table]

    purity = check_target_purity(contract, target, features)
    if purity:
        _refuse(purity)

    grain = check_grain_separation(manifest)
    if grain:
        _refuse(grain)

    output = next((o for o in manifest.outputs if o.name == table), None)
    if output is None:
        _refuse([f"table {table!r} has no output file in the manifest"])
    if sha256_bytes((directory / output.file).read_bytes()) != output.sha256:
        _refuse([f"{output.file} hash mismatch - the specimen is not intact; run verify"])

    table_text = (directory / output.file).read_text(encoding="utf-8")
    resolved_features = tuple(features)
    recorded_selector_params: tuple[tuple[str, float], ...] = ()
    if selector is not None:
        from .selectors import run_selector  # deferred: the [ml] blade, like the protocol itself

        non_numeric = [f for f in features if (c := contract.column(f)) is not None and c.type not in NUMERIC_TYPES]
        if non_numeric:
            _refuse([f"selection needs numeric features (float/int), got {non_numeric}"])
        assignment = read_split(table_text, _date_column(contract), manifest.splits)
        rows = list(csv.DictReader(io.StringIO(table_text)))
        x_train = [[float(rows[i][f]) for f in features] for i in assignment.train]
        y_train = [int(rows[i][target]) for i in assignment.train]
        if not y_train or len(set(y_train)) < 2:
            _refuse(["train segment has a single class - nothing to select on"])
        params = dict(selector_params or {})
        selection = run_selector(selector, x_train, y_train, tuple(features), seed, params)
        if not selection.features:
            _refuse([f"selector {selector!r} kept no features - nothing to train on"])
        resolved_features = selection.features
        recorded_selector_params = tuple(sorted((k, float(v)) for k, v in params.items()))

    records = runner(
        AssayContext(
            directory=directory,
            manifest=manifest,
            contract=contract,
            table_text=table_text,
            target=target,
            features=resolved_features,
            seed=seed,
        )
    )
    records = [
        replace(
            record,
            features=resolved_features,
            selector=selector,
            selector_params=recorded_selector_params,
        )
        for record in records
    ]
    appended = replace(manifest, assays=manifest.assays + tuple(records))
    write_manifest(appended, directory / "manifest.toml")
    return records


def _roc_auc(y_true: list[int], probability: Any) -> float:
    from sklearn.metrics import roc_auc_score

    return float(roc_auc_score(y_true, probability))


def _pr_auc(y_true: list[int], probability: Any) -> float:
    from sklearn.metrics import average_precision_score

    return float(average_precision_score(y_true, probability))


__all__ = ["PROTOCOL", "PROTOCOLS", "AssayContext", "ModelSpec", "run_assay"]
