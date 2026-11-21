# 可复用电路模块包

模块根目录由任务明确允许。目录形状为 `<root>/<module_id>/<revision>/module.json`。实际文件可以放在同一修订的 `circuit/`、`constraints/` 和 `verification/`。保留许可与来源页码。用户的私有模块放在单独允许根，不进入公开资产目录。

## 最小模板

以 [样板清单](../assets/module-packs/sar-adc-input/0.1.0/module.json) 为示例，对照 [Schema](../assets/module-pack.schema.json) 填以下内容。

| 必填核心 | 填法 |
| --- | --- |
| `schema/module_id/revision/variant/function/tags/scope` | 固定包身份、功能和适用阶段。采用 `hardware-module-pack-v1`。 |
| `provenance` | 登记来源、版本、许可及使用权限，只有获得再分发权的工件才能公开。 |
| `interfaces` 与 `conditions` | 给端口、方向、引脚或网络与参考域，工况按明确单位、区间或枚举填写。 |
| `parts` 与 `files` | 明确关键件完整 MPN、封装、引脚、DNP 与同版文件的相对路径、摘要和许可。 |
| `evidence` | `saved_eda`、`calculation`、`simulation`、`bench` 每层单独填。尚无证据填 `{"status":"pending","receipt":null}`。已核证据引用文件 ID 并声明范围。 |

可从样板复制骨架并替换为自己的受控文件。最小包可以省略 `forbidden_combinations`、`layout_constraints`、`allowed_changes` 和 `change_impact`。前两项省略返回未声明。后两项缺失时，参数偏离或 ECO 做保守重验，交给 `design_flow impact` 追踪项目范围。原有回执的可复用性按绑定的工况、版次和文件验证。

## 查找与使用

```powershell
python -X utf8 -B scripts/project_library.py module-search --library assets/module-packs --query adc-front-end
python -X utf8 -B scripts/project_library.py module-fit --library assets/module-packs --manifest sar-adc-input/0.1.0/module.json --conditions request.json
```

上述命令从 `hardware-project-library` 目录运行。请求对象给 `conditions`，数值形如 `{"source_ohm":{"value":50,"unit":"ohm"}}`。已有项目实例可列 `interfaces` 与 `changes`，每条变更给对象、现有工程 kind 和 before/after。

- `fits` 仅说明当前声明边界相符，进一步读各层证据状态。`recheck` 给需要重验的条件。`needs_input` 需要补充条件。`blocked` 拦截硬边界或禁止组合。
- 调用 `design_flow start` 时用 `--module-query` 及可选 `--module-conditions`。用户允许的外部根传 `--module-root`。发现可用包之后，固定修订、变体及清单摘要。ECO 将核对结果中的 `impact.changes` 与实际项目 baseline 组成现有 `hardware-engineering-change-v1`，把模块变体和对象映射到受影响的项目变体及实例后，再用 `design_flow impact`。检索过程只读本地清单与已声明文件。

样板检验一个低压、单通道、单端 SAR 前端接口。原生示例以文本夹具随包提供，按 `files.materialize_as` 复制到隔离目录，再用本机版本的 KiCad 生成和比对 XML 网表。原始 BOM、线性计算与 ngspice 模型分别关联证据。具体 ADC 的动态输入、抗混叠、布局和实测仍按项目要求验证。
