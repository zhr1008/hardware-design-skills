---
name: design-and-review-circuit
description: Design, audit, or correct an electronic circuit from a product brief, native schematic, netlist, block diagram, or circuit description. Use for architecture and component-function review, power and logic-domain checks, reset and boot sequencing, bus ownership, ratings, timing, protection, safe states, component suitability, circuit bugs, or layout-facing electrical constraints.
---

# Circuit Design Reviewer

涉及写入或派生制造工件时，按[保存态回读](../hardware/references/saved-design-readback.md)逐项核对同版真实工程及原生报告，记录回执、写入结果和实际覆盖。

按 [工程决策](../hardware/references/design-workflow.md) 的原型风险，主动对照 WCCA、非理想动态与故障状态。方案反证后保留实用可测点和隔离/吸收预留。仿真交工况、步长、所测目标和模型未覆盖范围。

工程设计、实质改版或审查先取得 [硬件设计流程](../hardware/references/design-workflow.md) 的要求、专项依据和判据。直接被点名且尚无这些输入时，按该流程主动补齐，再定器件和拓扑或下审查结论。复用已有同版证据。既定接线的制图和单点计算走各自短入口。

[SPICE 实验合同与读回](references/spice-readback.md)

电源环路、PDN、采样和时序预算见[电源与模拟审查](references/power-and-analog-review.md)。具备已审网表与测量合同的离线验收使用 [SPICE 批处理](scripts/run_spice.py)。

仿真先核已有网表、模型身份、求解器和测量窗口。Multisim 现场先核目标电路，仅查询该次分析需要的对象。COM、前台或原件写入按硬件门禁另行核权，超时后读回再处置。

Treat readability and electrical correctness as separate gates. A review request
stays read-only; a new-design or correction request authorizes the corresponding
implementation. Continue through the requested native circuit deliverable.

## Create or adapt a circuit

1. Reuse the supplied engineering brief and hardware/firmware interface contract.
   Find suitable manufacturer or company reference circuits with
   `hardware-project-library`; record exact source revision, conditions and the
   intended delta. A reference is not proof that the derivative works.
2. Establish operating states, block interfaces and accurate pin-to-net intent.
   Select exact parts and calculate relevant bias, feedback, current limit,
   filtering, timing, dissipation and tolerance margins from cited inputs.
   Verify passive ratings, capacitor DC bias/ESR and inductor saturation where
   relevant; schematic symbols alone do not establish component suitability.
3. Implement through the project's actual EDA/API or supported generator.
   Use DesignPlan and measured placement hints when the current eda-agent
   provides them; query its tool guide and exact contracts before acting.
   Adapt an existing board without silently replacing unrelated circuitry.
4. Save and reopen/read back the native source; compare canonical connectivity,
   inspect every sheet, run applicable ERC and simulation, then perform the audit
   below. Record known failures and untested dimensions separately.
5. Hand pin, polarity, power-state and timing changes to firmware as well as PCB.
   When no native editor is available, complete calculations and connection intent,
   but explicitly retain the native-circuit deliverable as incomplete.

## Establish truth

1. Use the applicable instructions and artifacts within the authorized source scope.
   For an existing design, inspect the relevant brief, schematic or generator,
   affected netlist, parts, interfaces and review evidence. For a standalone design,
   use the agreed inputs and the local knowledge basis.
2. Identify the electrical source of truth. When a generator owns the
   schematic, modify the generator rather than only generated files.
3. Capture ERC/lint, connectivity, and protected PCB/layout hashes before any
   authorized correction.
4. Use official manufacturer documents for exact orderable parts. Reuse verified
   local copies where applicable. Verify changing facts within the permitted sources;
   record gaps when the task limits source access.
5. Select the evidence path in
   [references/evidence-adapters.md](references/evidence-adapters.md); never
   claim an edit or verification stronger than the source permits.

## Audit

涉及快边沿、瞬态保护、器件应力或隔离屏障时，按 [工程核验](../hardware/references/engineering-verification.md) 记录最快有效边沿、终端、保护与回流路径、损耗和设计工况、隔离两侧与采用的限值。把实际约束交给 PCB，并标出需要仿真或量测的项。

涉及 SAR ADC 前端或电源瞬态预算时，引用 [工程预算](../hardware/references/engineering-budgets.md) 记录阶跃、实际采集窗或动态压降分配，交给 PCB 对应的网名、工况、测点与未验证项。

Use [references/circuit-audit-checklist.md](references/circuit-audit-checklist.md)
and deliver findings in the requested form. For an authorized recorded project,
use [assets/circuit-review.md](assets/circuit-review.md) to write
`.pcba-workflow/circuit-review.md`.

- Explain operating principle and data/power/control flow in plain language.
- Build a component-by-component function table, power tree, voltage-domain
  table, operating-state table, and reset/boot/ownership sequence.
- Trace every external interface, power entry, driver, receiver, memory/control
  path, and hardware default. Check partial-power and firmware-not-running states.
- Verify ratings, logic thresholds, enable polarity, unused pins, static ties,
  decoupling, regulator stability/thermal margin, protection, clocks/timing, and
  connector semantics.
- Classify each finding as critical, major, minor, or information; distinguish
  proven defect, design risk, and unknown evidence.
- Record layout constraints using `[SPEC]`, `[TARGET]`, or `[TBD-MEASURE]`.
  Include data/edge rate, topology and stubs, return plane, skew intent, current
  allocation, placement, keepout, and authoritative source where applicable.

## Correct only when authorized

For each change, state the defect and evidence, edit the source of truth, render
the complete schematic, inspect it visually, rerun ERC/lint, compare canonical
connectivity, and confirm protected layout files remain unchanged. A deliberate
electrical change must appear explicitly in the connectivity delta and design
decision record; do not hide it inside presentation cleanup.

## Gate

Use `PASS` only when no critical/major issue or safety-relevant unknown remains
and the selected parts match the sourcing lock. Use `USER_REVIEW` for explicit
engineering decisions and `BLOCKED` for missing evidence or a failed check.

Hand drawing readability to `$schematic-humanizer`, part risk to
`$qualify-pcba-sourcing`, and placement/routing constraints to
`$pcb-layout-review`.
