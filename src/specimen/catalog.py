"""Catalog: prepare (seal), load, verify and reproduce specimens.

A sealed specimen directory is

    <dir>/manifest.toml
    <dir>/<output file>...        (one per declared output)

``prepare`` runs a registered recipe over raw inputs, writes the outputs
(LF), computes their hashes and seals the manifest. ``verify`` checks a
directory four ways: manifest validity, output integrity (hashes), contract
conformance, and — when the raw inputs are supplied — bit-reproducibility
(invariant I4). Nothing in this module consults the clock or the platform.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from .contract import validate_all
from .hashing import sha256_bytes
from .manifest import Input, Manifest, Output, parse_manifest, validate_manifest, write_manifest
from .recipes import REGISTRY


def load_raw(raw_dir: str | Path, filenames: tuple[str, ...]) -> dict[str, bytes]:
    raw = {}
    for name in filenames:
        raw[name] = (Path(raw_dir) / name).read_bytes()
    return raw


def prepare(recipe_name: str, seed: int, raw: Mapping[str, bytes], out: str | Path, version: int = 1) -> Manifest:
    """Run a recipe and seal a specimen directory (idempotent, deterministic)."""
    spec = REGISTRY[recipe_name]
    missing = [name for name in spec.inputs if name not in raw]
    if missing:
        raise KeyError(f"raw inputs missing: {missing}")
    outputs = dict(spec.run(seed, {k: raw[k] for k in spec.inputs}))

    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    sealed: list[Output] = []
    for name in sorted(outputs):
        filename = f"{name}.csv"
        (out_dir / filename).write_text(outputs[name], encoding="utf-8", newline="\n")
        rows = max(outputs[name].count("\n") - 1, 0)
        sealed.append(
            Output(
                name=name,
                grain=next(c.grain for c in spec.contracts if c.name == name),
                file=filename,
                sha256=sha256_bytes(outputs[name].encode("utf-8")),
                rows=rows,
            )
        )
    manifest = Manifest(
        name=f"{recipe_name.replace('_', '-')}-s{seed}",
        version=version,
        seed=seed,
        recipe_module=spec.module,
        recipe_steps=spec.steps,
        inputs=tuple(Input(path=name, sha256=sha256_bytes(raw[name])) for name in spec.inputs),
        outputs=tuple(sealed),
        contracts=spec.contracts,
        splits=spec.splits,
    )
    problems = validate_manifest(manifest)
    if problems:
        raise ValueError(f"refusing to seal an invalid manifest: {problems}")
    write_manifest(manifest, out_dir / "manifest.toml")
    return manifest


def load(specimen_dir: str | Path) -> Manifest:
    return parse_manifest((Path(specimen_dir) / "manifest.toml").read_text(encoding="utf-8"))


def verify(specimen_dir: str | Path, raw: Mapping[str, bytes] | None = None) -> tuple[bool, list[str]]:
    """Check a specimen; returns (ok, report lines). With ``raw``, also I4."""
    directory = Path(specimen_dir)
    report: list[str] = []
    ok = True
    try:
        manifest = load(directory)
    except (OSError, KeyError, ValueError) as error:
        return False, [f"manifest: unreadable ({error})"]

    problems = validate_manifest(manifest)
    report += [f"manifest: {p}" for p in problems] or ["manifest: ok"]
    ok = ok and not problems

    for out in manifest.outputs:
        path = directory / out.file
        if not path.exists():
            report.append(f"integrity: {out.file} missing")
            ok = False
            continue
        digest = sha256_bytes(path.read_bytes())
        if digest != out.sha256:
            report.append(f"integrity: {out.file} hash mismatch (tampered or regenerated differently)")
            ok = False
    if ok:
        report.append("integrity: ok")

    tables = {
        out.name: (directory / out.file).read_text(encoding="utf-8")
        for out in manifest.outputs
        if (directory / out.file).exists()
    }
    contract_problems = validate_all(manifest.contracts, tables)
    report += [f"contract: {p}" for p in contract_problems] or ["contract: ok"]
    ok = ok and not contract_problems

    if raw is not None:
        reproduce_problems = _reproduce(manifest, raw, directory)
        report += [f"reproduce: {p}" for p in reproduce_problems] or ["reproduce: ok (byte-identical)"]
        ok = ok and not reproduce_problems
    return ok, report


def _reproduce(manifest: Manifest, raw: Mapping[str, bytes], directory: Path) -> list[str]:
    """I4: rerun the recorded recipe and compare every output byte for byte."""
    from .recipes import REGISTRY  # module recorded in the manifest is the lookup key

    spec = next((s for s in REGISTRY.values() if s.module == manifest.recipe_module), None)
    if spec is None:
        return [f"recipe module {manifest.recipe_module!r} is not registered"]
    missing = [name for name in spec.inputs if name not in raw]
    if missing:
        return [f"raw inputs missing: {missing}"]
    fresh = dict(spec.run(manifest.seed, {k: raw[k] for k in spec.inputs}))
    problems = []
    for out in manifest.outputs:
        current = (directory / out.file).read_text(encoding="utf-8")
        if fresh.get(out.name) != current:
            problems.append(f"{out.file} differs from a fresh run")
    expected_manifest = Manifest(
        name=manifest.name,
        version=manifest.version,
        seed=manifest.seed,
        recipe_module=manifest.recipe_module,
        recipe_steps=manifest.recipe_steps,
        inputs=manifest.inputs,
        outputs=manifest.outputs,
        contracts=manifest.contracts,
        splits=manifest.splits,
    )
    if render_differs(expected_manifest, manifest):
        problems.append("manifest fields differ from a fresh seal")
    return problems


def render_differs(a: Manifest, b: Manifest) -> bool:
    from .manifest import render_manifest

    return render_manifest(a) != render_manifest(b)


def catalog(root: str | Path) -> list[dict[str, object]]:
    """List sealed specimens under a root directory (name, version, outputs)."""
    entries = []
    for manifest_path in sorted(Path(root).glob("*/manifest.toml")):
        manifest = parse_manifest(manifest_path.read_text(encoding="utf-8"))
        entries.append(
            {
                "name": manifest.name,
                "version": manifest.version,
                "seed": manifest.seed,
                "outputs": [o.name for o in manifest.outputs],
                "dir": manifest_path.parent.name,
            }
        )
    return entries
