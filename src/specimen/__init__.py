"""Specimen G-Code: data you can testify about.

Phase 1 (2026-11-16): the manifest / contract / catalog core with golden
bit-reproducibility, zero-dependency, CSV tables. v0.2.0 (2026-11-18): the
manifest pins the recipe module's source hash, so verify distinguishes code
drift from input drift. Pipeline stages: acquisition -> preparation ->
staining -> catalog -> assay, held to the four invariants of
docs/DESIGN.md section 4 (time safety, target purity, grain separation,
bit-reproducibility).
"""

from __future__ import annotations

from .catalog import catalog, load_raw, prepare, verify
from .contract import parse_date, validate_all, validate_table
from .hashing import sha256_bytes, sha256_file
from .invariants import SplitAssignment, check_grain_separation, check_target_purity, check_time_safety, read_split
from .manifest import (
    ColumnSpec,
    Input,
    Manifest,
    Output,
    Splits,
    TableContract,
    parse_manifest,
    render_manifest,
    validate_manifest,
    write_manifest,
)
from .recipes import REGISTRY, RecipeSpec

__version__ = "0.2.0"

__all__ = [
    "REGISTRY",
    "ColumnSpec",
    "Input",
    "Manifest",
    "Output",
    "RecipeSpec",
    "SplitAssignment",
    "Splits",
    "TableContract",
    "__version__",
    "catalog",
    "check_grain_separation",
    "check_target_purity",
    "check_time_safety",
    "load_raw",
    "parse_date",
    "parse_manifest",
    "prepare",
    "read_split",
    "render_manifest",
    "sha256_bytes",
    "sha256_file",
    "validate_all",
    "validate_manifest",
    "validate_table",
    "verify",
    "write_manifest",
]
