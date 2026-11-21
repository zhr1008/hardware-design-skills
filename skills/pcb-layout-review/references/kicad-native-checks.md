# KiCad 保存态原生检查

```powershell
python -X utf8 -B scripts/run_kicad_checks.py board.kicad_pcb --output-dir path/to/new-check --kicad-cli path/to/kicad-cli
```

执行器通过扩展名选择 ERC 或 DRC。使用 KiCad 9.x/10.x 稳定版，保留命令、版本、退出码、原生 JSON 与日志。它在新目录复制保存态文件及适用的工程规则和库表，纳入本地层次原理图，可用 `--companion` 补充同一源目录范围内的文件。隔离配置使用安装自带的标准库表执行 ERC。源文件摘要在执行前后比对。

原生退出码 5 表示报告有违规，报告的排除、忽略以及严重度覆盖以实际 JSON 和已读回条目为准。本机实测 KiCad 9.0.7 的报告缺少 `included_severities`，正式结果保留 `coverage_incomplete`。其他工具错误、报告缺失和无效报告各有独立状态。单文件 DRC 覆盖 PCB 本身，原理图一致性检查在跳过记录中标明。

## 配对保存回读

```powershell
python -X utf8 -B ../hardware/scripts/hardware_tool.py kicad-native-check board.kicad_pcb --schematic board.kicad_sch --expected-readback intent.json --output-dir path/to/new-check
```

文件同目录同名根。预期 `kicad-saved-readback-v1` 清单含版次、变体、项目内相对文件名至 SHA-256 的明确映射、逐脚原理图 `schematic-connectivity-v1` 及 PCB 的位号／封装／全部编号焊盘数组。预期图由本次设计或经确认的 ECO 对照生成。固定输入副本后实际导出 KiCad XML、运行 ERC 和含原理图一致性的 DRC，留存原始输出与对账。正反例见仓库原生回归。回读过程本身只读，`mutation_outcome` 不替代前一写操作的结果。报告层有覆盖缺项时保留缺项。详见[保存态回读](../../hardware/references/saved-design-readback.md)。

## 确认自定义规则确实生效

评审使用的工程规则与工具默认规则分别确认。同一测试板上先用控制限值，再用故意触发的限值运行两次。两份报告应可定位到同一板摘要、不同规则摘要和目标规则名。示例的三个焊盘距板边 4.50 mm。把合成规则 `fixture_edge_clearance` 的最小值设为 1 mm 时无这项违规，改为 5 mm 时必须出现三项 `copper_edge_clearance`，且每项描述包含该规则名。板及其余检查结果独立保存。用例验证指定规则被加载及执行，项目限值取实际工艺文件。测试规则只放在隔离夹具，生产工程维持批准的规则。

已有报告仍用 `hardware_tool.py kicad-report-check`。需要新报告时从总入口调用 `hardware_tool.py kicad-native-check <board.kicad_pcb> --output-dir <新目录>`，或直接运行上文专项脚本。

保存态回归使用同一合成板的三项接点，分别核对 Altium 保存文件、KiCad 保存文件与 KiCad 原生 IPC-D-356 导出。范围包括位号、脚号、网络与装配面，空网络表示保存文件中未接网。该回归不推断设计意图、编译网表、装配变体或未保存窗口。基础回归使用现有连通性比较器，无外部 EDA 依赖。原生回归需要 KiCad CLI、KiCad 自带 Python 与 `altium-monkey`。

[KiCad 9 CLI](https://docs.kicad.org/9.0/en/cli/cli.html) · [KiCad 10 CLI](https://docs.kicad.org/10.0/en/cli/cli.html)
