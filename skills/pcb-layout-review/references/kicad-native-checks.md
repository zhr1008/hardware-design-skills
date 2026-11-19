# KiCad 保存态原生检查

```powershell
python -X utf8 -B scripts/run_kicad_checks.py board.kicad_pcb --output-dir path/to/new-check --kicad-cli path/to/kicad-cli
```

执行器通过扩展名选择 ERC 或 DRC。使用 KiCad 9.x/10.x 稳定版，保留命令、版本、退出码、原生 JSON 与日志。它在新目录复制保存态文件及适用的工程规则和库表，纳入本地层次原理图，可用 `--companion` 补充同一源目录范围内的文件。隔离配置使用安装自带的标准库表执行 ERC。源文件摘要在执行前后比对。

原生退出码 5 表示报告有违规，报告的排除、忽略以及严重度覆盖以实际 JSON 和已读回条目为准。本机实测 KiCad 9.0.7 的报告缺少 `included_severities`，正式结果保留 `coverage_incomplete`。其他工具错误、报告缺失和无效报告各有独立状态。DRC 当前覆盖 PCB 本身，原理图一致性检查在跳过记录中标明。

保存态回归使用同一合成板的三项接点，分别核对 Altium 保存文件、KiCad 保存文件与 KiCad 原生 IPC-D-356 导出。范围包括位号、脚号、网络与装配面，空网络表示保存文件中未接网。该回归不推断设计意图、编译网表、装配变体或未保存窗口。基础回归使用现有连通性比较器，无外部 EDA 依赖。原生回归需要 KiCad CLI、KiCad 自带 Python 与 `altium-monkey`。

[KiCad 9 CLI](https://docs.kicad.org/9.0/en/cli/cli.html) · [KiCad 10 CLI](https://docs.kicad.org/10.0/en/cli/cli.html)
