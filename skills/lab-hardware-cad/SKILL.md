---
name: lab-hardware-cad
description: Designs custom laboratory hardware as parametric build123d models and exports fabrication artifacts as STEP, STL, and DXF files - microfluidic chips and molds, optomechanical mounts and breadboard adapters, cuvette and microplate holders, tube racks, animal-behavior rigs, and 3D-printed instrument fixtures. Use when a research task needs a physical part that must mate with standardized labware, an optical table, a cage system, or a printer, CNC, or laser process.
license: MIT
allowed-tools: Read Write Edit Bash Glob Grep
metadata:
  version: "1.5"
  skill-author: K-Dense Inc.
  last-reviewed: "2026-10-01"
  build123d-version: "0.13.0"
---

Requirements: Python 3.11–3.14, build123d 0.13.0 for geometry, and matplotlib for snapshots. Standards lookup and interface checks use the standard library. Network access is used for installation and current vendor drawings. Local geometry checks run offline.

# Lab Hardware CAD

装配基准、跨公差链、板弯及涂覆边界见 [PCB 机电参考](../pcb-layout-review/references/materials-mechanics-and-environment.md)。

Design physical research hardware as **parametric Python source**, export STEP as the
authoritative artifact, and verify the result both numerically and visually before anything
is fabricated.

The hard part of lab hardware is almost never the geometry. It is that the part must mate with
equipment whose dimensions are fixed by a published standard or a vendor drawing. A holder that
is 0.5 mm too wide does not fit the plate reader; a channel with the wrong aspect ratio collapses
during bonding; a mount whose bolt pattern is 25.4 mm instead of 25.0 mm will not reach the
optical table. This skill exists to keep those numbers correct and checked.

## When to use

Use for any request to design, model, or fabricate a physical part for a lab: chip, mold, mount,
adapter, holder, rack, bracket, enclosure, jig, fixture, arena, or maze. Also use to inspect or
modify an existing STEP file.

Do **not** use for finite-element analysis, computational fluid dynamics, molecular structure,
or scientific plotting. Those are different skills.

## 建模与验收

先按 [建模工作流](references/parametric-cad-workflow.md) 选取设备家族和接口依据。逐一绑定尺寸来源、公差和工艺，建立参数化源模型。`scripts/gen.py`、`scripts/check.py` 和 `scripts/snapshot.py` 保留原有 CLI。模型文件会执行 Python，运行前确认其来源与内容。

交付模型前核对 STEP 的实体、配合、间隙、关键尺寸，并检查多视角渲染。需要返工时改参数化源并重新导出。确认制造版本、材料、工艺和例外后交制造专项。装配公差、板弯和涂覆见硬件 11 域索引的机电专题。
