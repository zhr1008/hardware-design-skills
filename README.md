# Hardware Design Skills

在 Codex 里查器件、画电路图、审查 PCB，或把一块板从需求推进到制造和台架验证。这个技能包包含 48 个可单独调用的技能。知道要用哪个专项时可以直接点名，需要按工件或交付物选入口时用 `$hardware`。

[下载安装](#安装) · [从一个任务开始](#在-codex-里怎么用) · [架构图](#架构与分工) · [模块手册](docs/architecture-guide.md) · [48 项技能索引](docs/skill-catalog.md)

## 在 Codex 里怎么用

| 可以这样问 | 这次会交付什么 |
| --- | --- |
| 「用 `$hardware` 画一张 RC 低通示意图，给 SVG。」 | Schemdraw 源码和 SVG。需要可编辑的工程原理图时，写明 Altium、EasyEDA Pro 或 KiCad。 |
| 「只读核对这份保存的 Altium 工程，按页列出器件数。」 | 工程成员、保存态的器件明细和无法解析的文件。若还需要未保存的编辑内容，再申请现场读取。 |
| 「审这路 ADC 前端，把需要验证的条件和资料页写出来。」 | 与器件和工况对应的规则、文档版次、物理页或印刷页，以及待计算或待测的项目。 |
| 「优先在我给的标准阻容索引里找料，缺项再查公开来源。」 | 符合规格的候选、缺证据的字段，以及适用的商品页或原厂资料。为工程确认选用时，可从已核对数据生成 AD 选型表。 |
| 「这份 BOM 只转档案 CSV，已有料号原样保留。」 | 按指定模板生成 CSV，读回核对列、位号、数量和料号。 |
| 「看这份 KiCad DRC JSON，把未连接项、禁用规则和覆盖缺口列出来。」 | 已有报告的只读汇总，附报告来源、版本和 SHA-256。 |
| 「投板前核对这版 BOM 和贴装坐标，TP1 不贴。」 | 缺贴、多贴、重复位号和坐标字段问题，以及两份输入的 SHA-256。 |
| 「用这份限值判定台架结果，标出超限、缺项和单位错误。」 | 对照板号、硬件版次、固件哈希和单位的逐项核对结果。 |

单项任务交付所问结果即结束。整板任务才需要把接口、版本和验证结果交给后续专项。

## 架构与分工

![硬件技能包总图。任务经过选路与权限检查，专项使用规则、已有工件和所需工具，读回证据并交付。](docs/architecture/hardware-design-skills.png)

`$hardware` 根据目标、已有工件、EDA 平台和授权选入口。`hardware-solution` 在整板项目里协调供电、通信、机械和固件接口。`manage-pcba-program` 管理 PCBA 阶段、工件版本、放行结果和变更后的重验范围。需要做多专项的冻结判定或归因时，由 `hardware-design-review` 汇总各项工程证据。

### 各模块怎么配合

| 模块 | 接收什么，交付什么 |
| --- | --- |
| [任务路由与权限](docs/architecture-guide.md#任务路由与权限) | 根据工件状态和真实工具动作选入口。执行前检查许可，在用户要求的交付点停止。 |
| [需求与整板协调](docs/architecture-guide.md#需求与整板协调) | 把目标和参考工程转成可测要求与接口约束，交电路、PCB、固件和测试。 |
| [工程知识与综合评审](docs/architecture-guide.md#工程知识与综合评审) | 查适用规则和资料页，把判据与工程证据对齐，给出通过、待验证或阻塞项。 |
| [器件选型与 BOM](docs/architecture-guide.md#器件选型与-bom) | 用规格、订购 MPN 和渠道编号核对器件。把原厂脚位、封装和资格结果交给库、BOM 或制造。 |
| [原理图、工程库与 PCB](docs/architecture-guide.md#原理图工程库与-pcb) | 按 Altium、EasyEDA Pro 或 KiCad 选择入口。交付可编辑工件，或给现有工件的只读检查结果。 |
| [电路仿真](docs/architecture-guide.md#电路仿真) | 对指定模型、输入和工况运行求解，给波形及量测。结果回到电路设计或评审。 |
| [机械与装配](docs/architecture-guide.md#机械与装配) | 用板框、孔位和结构约束做板壳匹配，交 CAD 和尺寸证据，回传 PCB 修改项。 |
| [固件与台架](docs/architecture-guide.md#固件与台架) | 接口约定进入固件构建，镜像绑定板号和测量结果。故障回到电路、固件或配置的源头排查。 |
| [制造包与供应商](docs/architecture-guide.md#制造包与供应商) | 冻结同版 Gerber、钻孔、BOM、CPL 及清单。按具体授权处理外部预览、报价和订单。 |

模块图给出每一步的输入、分支和交接点。按具体技能查职责时，可以直接打开 [48 项技能索引](docs/skill-catalog.md)。图标来自 [Lucide](https://lucide.dev/)。

### 以一块传感器采集板为例

先定采集范围、误差、供电与通信接口。器件专项用原厂资料核对采样前端和主控，留下完整 MPN、封装与脚位依据。电路专项输出原理图和关键网约束。PCB 与固件使用同一份板级接口约定，机械模块同时回传板框、孔位和连接器装配空间。

首板联调时，用板号、硬件版次和固件哈希绑定启动日志与测量结果。测量异常先确认是供电、前端、采样配置还是测试条件的问题，再回到相应专项。出包时绑定 PCB、BOM、CPL 和装配证据。如果贴装预览的方向有误，从库件、板上的放置或 CPL 导出查起。修正后重新生成并核对受影响的工件。

## 固定脚本与交付终点

从仓库根目录运行。

```powershell
python -X utf8 skills/hardware/scripts/hardware_tool.py list --json
python -X utf8 skills/hardware/scripts/hardware_tool.py --plan bom-archive bom.csv --output out/archive.csv
python -X utf8 skills/hardware/scripts/knowledge.py rules --domain PCB与EMC --summary
```

| 命令 | 输出 |
| --- | --- |
| `ad-saved` | 读取保存的 `.PrjPcb`、`.SchDoc` 或 `.PcbDoc`，给工程成员或对象数据。需要 `altium-monkey`。 |
| `bom-archive` | 预检 BOM 及映射。指定 `--output` 时生成档案 CSV 并读回。 |
| `selection-export` | 从已核对 JSON 生成 AD HTML 或按需生成 Excel。补 Excel 可用 `--xlsx-only`。 |
| `sourcing-lock-check` | 核对资格表字段、数量、费用及已记录证据的时效。 |
| `kicad-report-check` | 读取现有 KiCad 9/10 ERC 或 DRC JSON，列出违规、排除、禁用规则与覆盖范围。 |
| `assembly-check` | 对照同版 BOM 与 CPL，核对位号、DNP、板面、坐标格式和单位。 |
| `release-check` | 校验冻结制造包清单、版次、尺寸及 SHA-256。 |
| `bench-check` | 按输入限值核验台架测量，标出超限、记录无效与缺项。 |

`knowledge.py` 可离线查随包的 96 条审查规则。带 `--library` 时可读用户的全文索引，查题录、正文和页标。`ocr_books.py` 用于已整理的逐页 OCR，`pack_mineru_book.py` 可从现有 Middle JSON 建索引。器件专项另有批量查料、等条件分组和本地阻容筛选脚本。 [固定命令用法](skills/hardware/references/local-tools.md) · [知识库用法](skills/hardware/references/engineering-knowledge.md) · [器件批查与续跑](skills/component-sourcing/references/batch-lookup.md)

## 权限怎么划分

| 级别 | 典型动作 |
| --- | --- |
| L0 离线读取 | 读保存版工程、库、报告和本地测量数据。 |
| L1 定向只读 | 读已获准的活动文档，或查询公开料价。审查保存态时，转到活动工程需要单独核对许可。 |
| L2 有界本地操作 | 写指定副本、生成本地工件、构建、后台仿真，或不保存设计源的非模态编译。 |
| L3 原工程、前台、设备与外发 | 原工程写入、模态 DRC、桌面操作、烧录、主动发帧、仪器输出、上传、下单和付款。 |

一次调用的等级取其中影响最大的动作。Altium 从离线读取升级到现场桥接，再升级到桌面操作时，分别核对授权。工程和 3D 文件默认留在本机，外发需要针对文件和接收方批准。 [权限细则](skills/hardware/references/permission-gates.md)

## 安装

下载并解压 [最新技能包](https://github.com/zhr1008/hardware-design-skills/releases/latest)，或检出仓库。用 Python 3.11 或更新版本在仓库根目录运行。

```powershell
python -X utf8 scripts/install_skills.py --dry-run
python -X utf8 scripts/install_skills.py
```

默认安装到 `~/.agents/skills`。`--target` 可指定客户端实际读取的技能目录，也可以手动复制 `skills/` 下的平级目录。预检会列出同名冲突，已有内容相同的技能会跳过。重新打开技能会话后可用 `$hardware`。

技能、脚本和模板随包安装。Altium、EasyEDA、KiCad、SPICE、固件工具链和设备运行环境按项目配置。在线查料可接独立的 Component Sourcing MCP。自有知识、OCR 和工程文件通过使用者指定的本机路径接入。 [运行依赖](docs/backends.md) · [Component Sourcing MCP](https://github.com/zhr1008/component-sourcing-mcp)

## 验证与许可

Windows 和 Linux CI 检查技能元数据、相对链接、Python 语法、离线安装、固定工具和可发布内容。项目的原生 EDA、供应商和实体台架结果以实际工程的运行记录为准。

```powershell
python -X utf8 -m pip install -r requirements-dev.txt
python -X utf8 scripts/validate_bundle.py
python -X utf8 scripts/check_publication.py --tree HEAD
python -X utf8 -m unittest discover -s tests
```

自有内容采用 [MIT](LICENSE)。随包第三方文件保留各自版权和许可。 [来源与许可](THIRD_PARTY_NOTICES.md)
