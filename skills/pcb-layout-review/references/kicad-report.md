# KiCad 原生报告离线读回

已有 KiCad 9.x 或 10.x 的 ERC/DRC JSON 时直接用下列命令。把文件和源工程版次一起记录。读回在本机执行，无需启动 KiCad。

```powershell
python -X utf8 skills/hardware/scripts/hardware_tool.py kicad-report-check out/erc.json --kind erc
python -X utf8 skills/hardware/scripts/hardware_tool.py kicad-report-check out/drc.json --kind drc
```

返回源文件声明、KiCad 版本、报告 SHA-256、报告严重级别覆盖，以及按规则与分组计数的错误、警告和排除项。分组包括 ERC 图纸和 DRC 的布局违规、未连接项及原理图一致性项。`ignored_checks` 显示报告列出的禁用规则，空值表示报告未提供该字段。0 表示该报告各级别可见且无发现，1 表示发现需复核的项（含排除项和报告列出的禁用规则），2 表示输入无效或级别覆盖不足。

仅缺报告且任务已明确允许在隔离位置运行本地检查时，关于新建报告使用同工程版次的副本，并从 `kicad-cli ... --help` 核对版本参数。将工件指定为同目录的原理图与 PCB，设置明确的输出路径。以 KiCad 9/10 的官方命令为例：

```powershell
kicad-cli sch erc --format json --severity-all --exit-code-violations --output out/erc.json copy/Board.kicad_sch
kicad-cli pcb drc --format json --severity-all --schematic-parity --exit-code-violations --output out/drc.json copy/Board.kicad_pcb
```

记录原生命令行、退出码、日志和工程文件哈希。原生退出码 5 表示报告命中违规，仍应读回已生成的报告。若工具日志显示原理图取数失败，或未明确显示执行过一致性检查，空的 `schematic_parity` 数组无法证明 PCB 与原理图一致。读回结果还须结合被禁用规则、工程约束及专项复核，包括原始连通、关键网、机械和独立 CAM 检查。独立制造审查走 [制造包专项](../../release-pcba-fabrication/SKILL.md)。

部分早期 KiCad 9.x 产物没有 `included_severities`，即使运行时传了 `--severity-all`。工具会保留发现项计数并标记覆盖不足。需要以已核对的执行日志补足覆盖证据，或在合适的同版副本中使用能在报告声明覆盖的版本重新输出。

参考 [KiCad 9 CLI](https://docs.kicad.org/9.0/en/cli/cli.html)、[KiCad 10 CLI](https://docs.kicad.org/10.0/en/cli/cli.html)、[原生 DRC 报告实现](https://github.com/KiCad/kicad-source-mirror/blob/9.0/pcbnew/drc/drc_report.cpp)和 [DRC 使用 CLI 的一致性检查](https://github.com/KiCad/kicad-source-mirror/blob/9.0/pcbnew/pcbnew_jobs_handler.cpp)。
