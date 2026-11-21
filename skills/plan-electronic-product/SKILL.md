---
name: plan-electronic-product
description: Turn an electronic product idea, behavior description, reverse-engineering note, or incomplete circuit concept into a decision-ready engineering brief and architecture. Use before schematic design or audit when functions, operating states, power, interfaces, mechanics, production quantity, cost, or measurable requirements are missing or ambiguous.
---

# Electronic Product Planner

直接任务走现有专项。开放式任务沿用工作态台账，正式交接才按[系统契约和一页协议](../hardware/references/system-contract.md)固定共享事实。把台账中的目标、外部约束和验收语义归入需求，保留仍可行的选项及决定性未知。交接前试找不可同时满足的工况；反例回到需求来源，由目标 owner 裁决。

按 [工程决策](../hardware/references/design-workflow.md) 的 `start plan` 展开接口、电源、热、故障状态和验证分配。非关键未知可取有界默认并注明首板关闭方法。对比可取得的器件、调试可达性和代价。

涉及安全目标、故障反应时间或可靠性分配时，按[系统安全与需求](references/system-safety-and-requirements.md)核口径、需求派生和上下游签收。

Within the [hardware engineering workflow](../hardware/references/design-workflow.md),
turn the supplied inputs into measurable requirements and interfaces. Deliver the
requested plan directly when project records are outside scope. For an authorized
recorded project, produce `.pcba-workflow/product-brief.yaml` and
`.pcba-workflow/architecture.md`; leave unsupported fields open and pass the brief
forward within the existing implementation authorization.

Define requirements from the supplied inputs and reuse the applicable local knowledge.
Consult `hardware-project-library` only when reference projects are needed and within
the allowed sources. Keep applicability, editable artifacts and measured validation
separate. Record hardware/firmware
contracts for pin ownership, startup/fault states, power budgets and test access;
`hardware-solution` coordinates implementation when the task spans those domains.

## Workflow

1. Read applicable instructions and relevant supplied or explicitly in-scope
   requirements, diagrams, mechanics, firmware behavior and commercial constraints.
2. Use [references/intake-checklist.md](references/intake-checklist.md) to
   distinguish known facts, design targets, assumptions, and unresolved choices.
3. For a recorded project, use [assets/product-brief.yaml](assets/product-brief.yaml)
   in the project state directory and complete supported fields.
4. Describe system boundaries, actors, external connectors, major functional
   blocks, data and energy flow, operating modes, startup/shutdown/fault states,
   and ownership of shared resources. For a recorded project, use `architecture.md`.
5. For every interface, record voltage domains, direction, protocol or bus,
   nominal rate, edge-rate uncertainty, topology, cable/connector environment,
   and protection expectations.
6. Build a provisional power budget by rail and mode. Mark calculated or
   measured provenance; do not treat typical datasheet current as a guaranteed
   system maximum.
7. Record mechanical envelope, user-accessible parts, antenna/enclosure needs,
   programming and test access, expected quantity, target cost, lifecycle, and
   compliance context.
8. Ask the user only for unresolved choices that materially alter architecture
   or safety. Record the rest as explicit unknowns with an owner and next
   evidence needed.

## Gate

For recorded project state, set `status: PASS` only when downstream circuit and sourcing specialists can
work without guessing core behavior, power source, interfaces, physical limits,
or production intent. Use `USER_REVIEW` for a decision awaiting the owner and
`BLOCKED` for missing evidence that prevents safe progress.

Do not select exact components or approve a circuit in this skill. Hand exact
parts to `$qualify-pcba-sourcing` and electrical implementation to
`$design-and-review-circuit`.
