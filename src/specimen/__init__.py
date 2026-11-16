"""Specimen G-Code: data you can testify about.

Phase 0 — design finalized in docs/, no pipeline code yet. This package
exists so the skeleton installs and the contracts below have a home:

  acquisition -> preparation -> staining -> catalog -> assay

with four invariants (docs/DESIGN.md section 4): time safety, target
purity, grain separation, bit-reproducibility.
"""

from __future__ import annotations

__version__ = "0.0.1"

__all__ = ["__version__"]
