# Hardware Design Skills

一套可安装的中文优先硬件工程技能。用 `$hardware` 选择最短的任务路径，也可直接调用包内专项。覆盖从需求、电路与 PCB、器件与库、仿真、固件和台架到制造交接。

首版随包提供 48 个技能，包含各自的说明、脚本、模板和工作流。

## 安装

下载 GitHub Release 源码包或检出仓库。解压后在仓库根目录用 Python 3.11 或更新版本运行：

```powershell
python -X utf8 scripts/install_skills.py --dry-run
python -X utf8 scripts/install_skills.py
```

默认目标为 `~/.agents/skills`。可以用 `--target` 指定当前客户端实际读取的技能目录，也可以直接复制 `skills/` 下的平级目录。安装器会先检查所有同名项，跳过内容相同的公开文件。冲突发生时先报告并保留既有技能。重开技能会话后可调用 `$hardware`。

## 包内能力

| 类别 | 主要入口 |
| --- | --- |
| 路由、权限和完整项目 | `hardware`、`hardware-solution`、`hardware-project-library`、`plan-electronic-product`、`manage-pcba-program` |
| 画电路图和处理、审查工程 | `draw-schemdraw-circuit`、`design-and-review-circuit`、`schematic-analyzer`、`schematic-humanizer`、`hardware-design-review`、`pcb-layout-review` |
| Altium 与 EasyEDA Pro | `altium-library`、`altium-schematic-review`、`altium-pcb-review`、`easyeda-agent`、`autodesign` |
| 器件、BOM、制造与机械 | `component-sourcing`、`ee-datasheet-master`、`bom-material-archive`、`qualify-pcba-sourcing`、`release-pcba-fabrication`、`operate-jlcpcb-order`、`fictiv`、`lab-hardware-cad` |
| 固件、调试与台架 | `embedded-firmware-design`、`embed-ai-tool`、`workflow`、各构建/烧录/调试专项、串口、CAN、Modbus、逻辑分析仪与 VISA |

技能正文、随包脚本、模板和资料按各目录归属安装。第三方来源与需要单独安装的工具见 [来源与许可](THIRD_PARTY_NOTICES.md) 和 [运行依赖](docs/backends.md)。

## 示例

- 「用 `$hardware` 画一张已明确拓扑的 RC 低通示意图，输出 SVG。」
- 「用 `$hardware` 批查这份保存的 Altium 工程，按页列器件数。」
- 「把这份 BOM 转档案 CSV，保留原位号、数量、层级和前导零。」
- 「核对这份制造包清单和文件哈希，交付本地复核结果。」

固定批处理可在终端查看和直接调用：

```powershell
python -X utf8 skills/hardware/scripts/hardware_tool.py list
python -X utf8 skills/hardware/scripts/hardware_tool.py --plan bom-archive bom.csv --output out/archive.csv
```

按交付目标选择执行深度。查询只取所需数据，明确出图时按交付格式选择示意图、EDA 原理图或仿真。会改变工程、控制前台或设备，以及上传和下单的动作按 [权限门禁](skills/hardware/references/permission-gates.md) 核对具体授权。

## 验证与许可

发布包含可离线核对的技能结构、安装、离线脚本及合成样例。原生 EDA、供应商、终端设备和实际制造各按本次运行留存证据。自有内容采用 [MIT](LICENSE)，随包第三方文件保留各自版权和许可证。
