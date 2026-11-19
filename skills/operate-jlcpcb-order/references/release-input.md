# Required release input

The operator accepts only `pcba-release-manifest-v1` with `status: PASS`.
Recompute every listed SHA-256 and require one revision across the native board
source/project, Gerber, drill, BOM, CPL, constraints, top/bottom renders,
circuit review, schematic connectivity/visual audit, layout review, and
sourcing lock.

Before any upload, require:

- `unexplained_raw_disconnects`, `real_drc_errors`, and
  `layout_check_failures` equal zero;
- circuit, layout, raw connectivity, power connectivity, visual/mechanical,
  DFM, sourcing freshness, and revision reconciliation equal `PASS`;
- direct reconciliation of the frozen BOM and CPL CSVs, including any recorded
  explicit exclusions, with both input hashes matching the listed artifacts;
- positive board dimensions, layer count, thickness, PCB/assembly quantities,
  and declared finish and assembly side;
- any required design-critical substitution separately approved with evidence.

Run `release-pcba-fabrication/scripts/validate_release_manifest.py` or an
equivalent check of the complete contract. A v1 manifest without a stored
assembly record still requires direct validation of the listed BOM and CPL.
Continue only with a verified `PASS` manifest and matching hashes.
