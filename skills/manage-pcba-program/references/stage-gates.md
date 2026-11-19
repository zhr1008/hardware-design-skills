# Stage gates and invalidation

## Gates

| Stage | Pass condition |
|---|---|
| `product_definition` | Functions, environment, power, interfaces, mechanics, quantity, cost target, and unknowns are recorded. |
| `sourcing` | Critical MPNs, packages, pinouts, lifecycle, stock, cost, CAD, 3D models, and substitution bounds are verified with dated evidence. |
| `circuit` | Locked parts pass architecture, ratings, power, reset, timing, safe-state, and ERC or equivalent review. |
| `schematic_visual` | Functional flow is visibly traceable, visual audit passes, and connectivity is unchanged or limitations are explicit. |
| `placement` | Functional corridors, connectors, decoupling, mechanics, RF, polarity, and package bodies pass logical and visual review. |
| `routing` | No unexplained disconnects or real DRC errors remain; return paths, planes, critical nets, and manufacturing constraints pass. |
| `manufacturing_release` | Gerber, drill, BOM, CPL, constraints, and source files share one revision and verified hashes. |
| `assembly_placement` | Supplier import passes complete machine reconciliation and visual pin/pad/polarity review with explicit user approval. |
| `order` | Parts, substitutions, options, price, shipping address, and payment are separately reviewed and explicitly approved. |

## Invalidation map

- `netlist` or `circuit`: circuit through order.
- `product-definition`: every stage.
- `mpn-package`: sourcing through order.
- `footprint` or `placement`: placement through order.
- `routing`: routing through order.
- `bom`: sourcing, manufacturing release, assembly placement, and order.
- `cpl`: manufacturing release, assembly placement, and order.
- `browser-placement`: manufacturing release, assembly placement, and order;
  mark manual browser edits present. The source CPL and release hash must be
  regenerated before the placement gate can pass again.
- `stock-price`: sourcing and order only unless the chosen part changes.

An invalidated stage is `BLOCKED`, not merely pending, because downstream work
must not proceed until it is repeated.

## Manufacturing release evidence

All `PASS` and `USER_REVIEW` stages and all approval decisions require nonempty
text in each `--evidence` entry. Evidence texts identify the engineering record
or approval. The program state validates the record format and prerequisites.
Other specialist reviews still follow their own procedures.

Record manufacturing PASS with the fabrication specialist installed alongside
this skill so the state command can verify the same release contract:

```powershell
python -X utf8 skills/manage-pcba-program/scripts/program_state.py set-stage `
  --stage manufacturing_release --status PASS --evidence "Reviewed release A" `
  --release-manifest release/A/release-manifest.json
```

The command records the verified manifest and CPL paths, revision, and SHA-256
in `artifacts`. Validation of an existing manufacturing PASS rechecks the files
and compares the recorded values. State command `PASS` with
`scope: program_state` indicates a valid state file. Each `stages` entry reports
its own gate outcome. For an older unbound manufacturing PASS, invalidate the
applicable change (such as `cpl`) and record the actual release again.

### Browser placement recovery

1. Record `invalidate --change browser-placement --reason ...`. The state
   preserves the last verified manifest and CPL hashes as the recovery baseline.
2. Apply the correction at the source, regenerate CPL, and build and verify a
   new release manifest. `invalidate --change cpl` keeps browser recovery pending.
3. Record manufacturing PASS with the new `--release-manifest` and evidence.
   The verified manifest and the CPL listed in it must both have SHA-256 hashes
   different from their pre-edit values. This clears the browser edit flag and
   records the two new hashes. Redo supplier reconciliation, visual review, and
   approval for the new release.

If older state history shows a browser edit without verified recovery, it is
still pending. If the pre-edit hashes were never recorded, supply the original
frozen package as `--previous-release-manifest` when recording the replacement.
If that package cannot be verified, the CLI cannot establish the comparison.
Keep the source export and supplier placement review as engineering evidence.

## Approval transitions

Use one explicit transition; do not collapse technical evidence into user
approval:

1. Complete machine reconciliation and full visual placement review, then set
   `assembly_placement` to `USER_REVIEW` with evidence.
2. Record the user's independent assembly-placement approval, then set that
   stage to `PASS` with the approved evidence.
3. After every prior stage is PASS, set `order` to `USER_REVIEW` with the final
   quote and address evidence.
4. Record final-price approval, then payment approval. Payment requires the
   substitution/no-substitution, assembly-placement, and final-price approvals
   already be APPROVED.
5. Set `order` to `PASS` only after all four approval records are APPROVED.

Placement may transition to `USER_REVIEW` or `PASS` only while sourcing is PASS.
A later stock/price-only refresh can block sourcing and order without
invalidating the already-proven physical placement.
