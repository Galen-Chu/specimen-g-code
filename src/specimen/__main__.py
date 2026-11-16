"""CLI: specimen prepare / verify / catalog (docs/DESIGN.md §2)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .catalog import catalog, load, load_raw, prepare, verify
from .recipes import REGISTRY


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="specimen",
        description="Deterministic specimen preparation: raw data in, a sealed, reproducible data bundle out",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    prep = commands.add_parser("prepare", help="run a registered recipe and seal a specimen")
    prep.add_argument("recipe", choices=sorted(REGISTRY))
    prep.add_argument("--seed", type=int, default=0)
    prep.add_argument("--raw", type=Path, required=True, help="directory holding the recipe's raw inputs")
    prep.add_argument("--out", type=Path, required=True, help="specimen directory to seal")

    check = commands.add_parser("verify", help="check a sealed specimen (integrity, contracts, I4 with --raw)")
    check.add_argument("specimen", type=Path)
    check.add_argument("--raw", type=Path, help="directory holding the raw inputs, to also verify bit-reproducibility")

    listing = commands.add_parser("catalog", help="list sealed specimens under a root directory")
    listing.add_argument("root", type=Path)

    args = parser.parse_args(argv)
    if args.command == "prepare":
        spec = REGISTRY[args.recipe]
        manifest = prepare(args.recipe, args.seed, load_raw(args.raw, spec.inputs), args.out)
        print(f"sealed {args.out}  ({manifest.name} v{manifest.version}, {len(manifest.outputs)} outputs)")
        return 0
    if args.command == "verify":
        raw = None
        if args.raw:
            manifest = load(args.specimen)
            raw = load_raw(args.raw, tuple(i.path for i in manifest.inputs))
        ok, report = verify(args.specimen, raw)
        for line in report:
            print(line)
        print("verify: PASS" if ok else "verify: FAIL")
        return 0 if ok else 1
    for entry in catalog(args.root):
        print(f"{entry['name']:24} v{entry['version']}  seed {entry['seed']}  outputs: {', '.join(entry['outputs'])}")  # type: ignore[arg-type]
    return 0


if __name__ == "__main__":
    sys.exit(main())
