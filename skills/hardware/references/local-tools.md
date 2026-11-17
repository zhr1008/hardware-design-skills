# 硬件批处理用法

从 `hardware` 目录运行下列命令，或使用脚本的绝对路径。输出适合直接交给下游程序或简短汇总。已有明确输入与许可的任务可以直接运行。查看某次调用的已解析输入、输出和风险级别时，在子命令前放 `--plan`。预览表示路径和参数的预检，文件内容与下游依赖在实际操作中验证。

```powershell
python -X utf8 scripts/hardware_tool.py list
python -X utf8 scripts/hardware_tool.py list --json
python -X utf8 scripts/hardware_tool.py ad-saved "D:/project/Board.PrjPcb" --kind schematic --designator R12
python -X utf8 scripts/hardware_tool.py ad-saved "D:/project/Board.PrjPcb" --document "sheets/Power.SchDoc" --json
python -X utf8 scripts/hardware_tool.py bom-archive BOM.csv
python -X utf8 scripts/hardware_tool.py bom-archive BOM.xlsx --sheet BOM --evidence reviewed-parts.json --output out/archive.csv
python -X utf8 scripts/hardware_tool.py selection-export selection.json --output out/ad
python -X utf8 scripts/hardware_tool.py selection-export selection.json --output out/ad --xlsx-only
python -X utf8 scripts/hardware_tool.py sourcing-lock-check sourcing-lock.csv
python -X utf8 scripts/hardware_tool.py release-check out/release-manifest.json
```

## 固定命令契约

| 子命令 | 执行与停点 |
| --- | --- |
| `ad-saved` | 只读已保存文件。项目调用按工程成员批查，可按文件和位号收窄，默认简要报告，`--json` 输出结构化明细。报告缺失、越界及无法解析的成员。保存态证据用于结构盘点，原生编译、ERC、DRC 和活动编辑态分别按各自入口处理。 |
| `bom-archive` | 预检返回缺项与冲突。指定 `--output` 后由物料档案专项生成 UTF-8 BOM/CRLF CSV 并读回。详见 [BOM 批处理](../../bom-material-archive/references/bom-archive-tool.md)。 |
| `selection-export` | 复用 [选型导出器](../../component-sourcing/references/ad-selection-export.md)。可用 `--draft --write-rows draft.json` 从候选保留证据并形成待核对底稿，正式出表使用已核对 JSON。Excel 按显式参数生成。更新已授权的现有表时加 `--replace-output`。 |
| `sourcing-lock-check` | 核对已有资格表的字段、数量与证据时效。表内证据与本次真实供货查询各按实际记录。 |
| `release-check` | 校验已有制造包清单和文件内容。工件路径以清单目录为根，验证版次、尺寸、哈希及已填写的门槛证据。CAM、DRC、上传和下单由相应专项处理。 |

脚本只向选中的本机专项传递固定参数，保留下游退出码和报告。对于字面输入、重名文件、缺项或权限错误，依返回的具体原因决定后续动作。一次任务只读取匹配项的帮助或引用即可。

## 复用已有入口

- 固件的 Keil、CMake 和 PlatformIO 流水线用 [workflow runner](../../workflow/scripts/workflow_runner.py)。`--dry-run` 输出步骤预览。执行时复核项目、目标、探针、端口和实编译产物，设备写入按 L3。
- SPICE 批量扫参与输出量测用当前暴露的 `ltspice-mcp` 的 `run_experiments`，将案例、参数变化和量测一次提交。检查输入网表和导入项，按实际仿真和窗口副作用核对权限。
- 只查精确 C 号、库存或资料时，用当前 `components` 的对应聚焦只读工具。选择、下载、导出和现场工作按用户实际要求触发。
