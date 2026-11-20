# 正式检查证据与后端探测

工程决策用 [正式工件与停点](design-workflow.md#正式工件与停点) 按版次/变体和实际工况消费证据。 `hardware_tool.py sourcing-lock-check LOCK.csv --formal` 包装专项 v2 的结果及同一次读取的 CSV 摘要，通过只表示资格与商务字段的适用检查。评估替料时用器件事实、原厂条款、CAD 映射和实际工况另行关闭电气问题。失败和缺据保留原字段及退出码。

现有 KiCad 报告检查、制造清单验证和台架结果检查均接受 `--formal`。继续使用原有 JSON、清单与 CSV。省略该参数沿用原有输出。

```powershell
python -X utf8 -B scripts/hardware_tool.py kicad-report-check board-drc.json --kind drc --formal
python -X utf8 -B scripts/hardware_tool.py release-check release/manifest.json --formal
python -X utf8 -B scripts/hardware_tool.py bench-check limits.json --measurements measurements.csv --formal
python -X utf8 -B scripts/evidence_adapter.py validate evidence.json
python -X utf8 -B scripts/evidence_adapter.py validate evidence.json --verify-artifacts
```

[证据包络 v1](../assets/evidence-envelope.schema.json)保留原检查器结果、工件 SHA-256 与覆盖范围。用 `execution_status` 表示读回或原生执行状态，用 `mutation_outcome` 表示目标的变化状态，用 `verification_status` 表示本次证据所支持的结论。可定位工件与已执行检查共同支撑 `pass`、`fail` 和 `no_reported_findings`。`invalid`、`missing`、`coverage_incomplete` 和 `not_evaluated` 分别保留。检查未执行时，`checks_skipped` 记录名称与原因。

- KiCad 的 `no_reported_findings` 仅针对报告列出的范围。单独读回一份已有报告时，原生规则执行状态未知。
- 制造清单验证读取审批与验证记录，并按合同核对版次、文件和适用的装配数据。包络保留清单、版次及本次 SHA-256 和尺寸均已核对的 `inputs.package:<role>` 工件。
- 台架记录比对按限值核对板号、硬件版次与固件摘要。读取已有 CSV 的检查不包含本次设备身份读回或物理量测。

格式校验通过时返回 `valid_format`。下游使用工件前加 `--verify-artifacts`，重新读取列出的本地文件，逐项返回 `match`、`changed`、`missing` 或 `unreadable`。任一项缺失或变化时退出 2，保留原报告并把待验项退回产生证据的专项。全部匹配只确认本地文件字节与记录一致。规则覆盖、项目适用性、可信审批及记录没列到的文件仍按各自的证据确认。包络使用绝对本地路径，若整体迁移则在新路径重跑支持的检查器取得交接报告。只给轻量结论时无需这一步。

使用 [backend_doctor.py](../scripts/backend_doctor.py) 查看[后端合同](../assets/backend-contracts.json)和本机可确认的版本。可选 `--backend` 限定范围，`--kicad-cli` 和 `--ngspice-cli` 接受本机路径，`--sourcing-repo` 读取独立查料仓库的版本与 Git 提交。

- `declared` 表示已有合同。Python 的 `installed` 只依据当前解释器分发元数据，CLI 依据可执行文件定位。CLI 的 `call_verified` 对应本次版本探测。
- `--runtime-observation` 读入显式保存的 `hardware-runtime-observation-v1`。其中 `backends.components` 保存带时区的 `observed_at`、对应工具名到 input schema 的 `tools` 映射，以及可选 `read_only_call`。回执有 `tool`、`status` 和 `input_schema_sha256`，摘要按键排序、UTF-8 和紧凑 JSON 计算。签名漂移、失败回执、未知与已观测成功分别显示。
- MCP 快照带有观测时间并显示 `current_session_probed: false`。诊断器不启动供应商服务、不探测生产接口，也不读取凭据。
