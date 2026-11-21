# 三档工程推进与系统契约

查料、单点计算、既定接线绘图和低风险局部改值直达专项。工作态在当前任务中维护目标与工况、候选与剪枝、决定性假设与反证、证据与裕量、下一步或回溯点。每轮推进最能改变决定的一项验证，只更新受影响条目。提交前挑选实际可达的反例，用独立工件或方法核对。证据冲突先核身份和工况，随后回到参数、接口分配或拓扑并重验依赖；无新增信息时结束重复尝试。

正式跨阶段交接、多变体 ECO 和放行才增加持久契约。单阶段正式审查沿现有 case。

## 工件归属

| 工件 | 维护的事实 |
| --- | --- |
| `product-brief.yaml` | 外部承诺、需求、使用条件和验收语义 |
| `architecture.md` | 人读图和取舍，引用需求与契约 ID |
| `system-contract.json` | 指定修订和变体的功能块、接口、预算、派生判据及依赖 |
| `case.json` | 检查、工况、判据、观察与实际证据 |
| `program-state.json` | 里程碑、失效、签核和批准来源 |
| `sourcing-lock.csv` | 指定变体的采购资格、来源、生产配置及采购时效 |
| `release-manifest.json` | 冻结件路径、摘要、实际制造参数及冻结证据 |

brief 与上游工件先固定，再形成契约和独立回执。最终放行 case 引用实际制造清单与 CPL，制造清单可以引用既有上游审查回执。项目状态最后记录 case 与清单。操作批准与工程证据独立。

## 派发和回传

以一个可验收动作交接。工作态可直接传同语义的短段落。本轮设计自主范围只约束可调整内容，操作许可来自用户或宿主。

| 包 | 字段 |
| --- | --- |
| 派发 | `id, baseline` 指定修订/变体及必要时的契约摘要。`task, slice, keep` 给动作、受影响事实和保持项。`close` 给测点、工况、判据及回读结果。`autonomy` 限定对象、可调范围、副本和停点。 |
| 回传 | `id, baseline, changes` 给实际差异、对象、变体和变化类别。`readback, margins` 给独立回读及适用裕量。`counterexamples, gaps` 给反例、影响源头和补证。无变化或反例可用空列表。 |

规划负责需求，系统设计负责端口与预算，综合评审负责独立反证，项目管理消费工件状态。`$hardware` 维护台账、下一动作和源头回溯。

## 正式检查

按 [Schema](../assets/system-contract.schema.json) 写项目内 `.pcba-workflow/system-contract.json`，case 的 `artifacts.system_contract` 固定项目相对路径及 SHA-256。

```powershell
python -X utf8 -B scripts/design_flow.py contract-check --root <project> --case <case> --contract <contract>
python -X utf8 -B scripts/design_flow.py assess --root <project> --case <case> --target handoff --require-system-contract
python -X utf8 -B scripts/design_flow.py impact --root <project> --case <case> --change <eco>
```

用 `contract:condition:<ID>`、`contract:criterion:<ID>` 引用判据，同样的字段传给 `bind`。绑定摘要包含当前变体、实际工况与判据；阈值或工况变化后须重新取证。结果为 0 覆盖、1 硬冲突、2 缺证。摘要不符、异变体、循环依赖、合计预算超限、工况与判据错配是硬冲突。缺文件、未知引用及无契约绑定的证据需要补证。

正式状态转换用 `set-stage --engineering-case <case> --require-system-contract` 显式要求契约。已有 case 可沿用旧入口。ECO 的 `enclosure-thermal` 类用于板壳结构和导热界面。传基线案例和变更给 `impact`，契约依赖和既有静态策略取并集，只重验受影响的变体。其他变体复用前核身份、工况和证据覆盖。
