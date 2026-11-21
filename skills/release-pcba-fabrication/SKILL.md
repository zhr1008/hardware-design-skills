---
name: release-pcba-fabrication
description: Build and verify a vendor-neutral PCB/PCBA manufacturing release from one frozen design revision. Use when generating or auditing Gerber, drill, IPC-2581/ODB++, BOM, CPL/pick-and-place, assembly drawings, constraints, renders, DFM evidence, hashes, or release manifests, and when preventing mixed-revision fabrication or assembly uploads.
---

# PCBA Fabrication Release

涉及写入或派生制造工件时，按[保存态回读](../hardware/references/saved-design-readback.md)逐项核对同版真实工程及原生报告，记录回执、写入结果和实际覆盖。

正式冻结前用 [工程决策](../hardware/references/design-workflow.md) 的 `assess --target fabrication` 核同版工件及证据。首件/量产用独立 `production` 目标，绑定批次、工装和实际测试。校验文件、项目签核、供应商动作分别处理。

[CAM 工件合同与读回](references/cam-readback.md)

正式冻结用 `validate_release_manifest.py --formal` 绑定本版证据，保存的 Gerber/钻孔可由 [CAM 离线读回](scripts/check_cam.py) 核查。结果按已解析工件的覆盖范围交接。

For a hardware/firmware product, bind the board revision to the intended firmware
build, programming/calibration instructions and test compatibility in the handoff.
Keep manufacturing-file checks, successful firmware build and physical validation
as distinct evidence. Do not report a software or sample-test result as production
qualification. Reuse `hardware-project-library` provenance when the design is a
derivative, and retain the deliberate changes to its original reference.

Release artifacts; do not redesign the circuit or layout inside this stage.
Read [references/release-checklist.md](references/release-checklist.md) and
[references/eda-release-adapters.md](references/eda-release-adapters.md).

## Preflight

制造数据和测试交接按 [DFM／DFT 核验](../hardware/references/dfm-dft-verification.md) 对照已确认的板厂工艺、实际出件与装配变体。项目有生产测试门槛时，冻结实际目标故障清单与证据，不把已放测试点当成已检出。

1. Read repository rules, sourcing lock, circuit/layout gate results, approved
   waivers, native board/project files, fabrication constraints, quantities,
   and target manufacturer capabilities.
2. Freeze one named source revision and record board/project hashes. Stop if
   schematic, PCB, BOM, CPL source, sourcing lock, or constraints disagree.
3. Require circuit and layout gates to be PASS. Zero opens alone is not enough:
   raw connectivity, real DRC, power connectivity, planes, critical nets,
   mechanical and visual review must all be resolved.

## Generate

Use the authoritative EDA tool to export all applicable layers, solder mask,
paste, silkscreen, outline/cutouts, mechanical information, plated/non-plated
drill, drill map/report, BOM, CPL, assembly drawings, stackup/impedance notes,
and top/bottom renders. Preserve units, origin, side convention, rotation
convention, DNP policy, polarity, and pin-1 evidence.

For saved BOM and placement CSVs, run the [offline assembly check](references/assembly-check.md)
to flag missing or repeated references, placement for DNP parts, and malformed
placement fields. The manifest builder and validator repeat this check against
the release artifacts for `PASS` and bind the result to their two hashes.

Inspect the generated files in an independent Gerber/assembly viewer. Compare
outline and dimensions, layer count, copper/mask, drills, text, apertures,
keepouts, edge treatments, panel/depanel needs, and assembly side. Export a
via/drill histogram and identify every feature below the current standard-cost
process threshold.

## Manifest

Build `.pcba-workflow/release-manifest.json` with
`scripts/build_release_manifest.py`. Supply an explicit revision for every
artifact; the script rejects mixed revisions. Record:

- source and derived artifact SHA-256, size, role, and revision, plus the
  generated BOM/CPL reconciliation evidence for a `PASS` release;
- board dimensions, layers, thickness, finish, stackup, controlled options,
  quantities, assembly side, and DNP policy;
- ERC, raw connectivity, classified DRC, power, layout, DFM, and visual results;
- approved waivers and the sourcing-lock hash/time;
- substitution, placement, final-price, and payment approval state.

Run `scripts/validate_release_manifest.py` after moving or packaging the
release. A missing file, hash drift, mixed revision, stale sourcing lock,
assembly side mismatch, or failed required check blocks release. Verify that
the declared assembly faces exactly match the placements in the frozen CPL.

In a recorded workflow, append checkpoints for the frozen source revision,
independent Gerber/drill inspection, BOM/CPL reconciliation, renders, and the
validated release manifest. Promotion frames may show sanitized viewers, but
the machine-readable release and hashes remain the approval evidence.

## Handoff

Deliver an immutable release directory containing the manifest, manufacturing
files, assembly files, constraints, and review evidence. State the exact upload
Gerber/archive, BOM, and CPL. Hand live supplier interpretation to
`$operate-jlcpcb-order`; it must not silently repair this release.
