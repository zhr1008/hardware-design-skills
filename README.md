# Hardware Design Skills

面向电子硬件设计、固件与验证的 **48 项可独立调用技能**。可以在 Codex 里查器件、画电路、审查 PCB，也可以从需求推进到板级联调和制造包冻结。跨专项任务用 `$hardware`，由它根据目标工件、平台和授权选择入口。

[快速开始](#快速开始) · [使用示例](#在-codex-里怎么用) · [架构图](#架构与分工) · [48 项技能速览](#48-项技能速览) · [模块手册](docs/architecture-guide.md) · [更新日志](CHANGELOG.md)

## 快速开始

### 安装

下载并解压[最新技能包](https://github.com/zhr1008/hardware-design-skills/releases/latest)，或检出仓库。用 Python 3.11 或更新版本在仓库根目录运行。

```powershell
python -X utf8 scripts/install_skills.py --dry-run
python -X utf8 scripts/install_skills.py
```

安装器默认写入 `~/.agents/skills`。用 `--target` 可指定客户端实际读取的目录。预检会列出同名冲突，相同内容会跳过。也可以手动复制 `skills/` 下的平级目录。重新打开技能会话后，用 `$hardware` 或点名具体技能。

### 查看可选后端

技能说明、固定脚本和模板随包提供。EDA、仿真器、固件工具链和仪器按工程配置。下列命令查看包内声明的可选后端及本机可取得的版本证据。CLI 会做版本探测，MCP 连接及调用状态可随已有观测记录查看。[运行依赖](docs/backends.md) · [后端诊断字段](skills/hardware/references/evidence-and-backends.md)

```powershell
python -X utf8 skills/hardware/scripts/backend_doctor.py
```

## 在 Codex 里怎么用

知道要用哪个专项时可以直接点名。例如查料用 [component-sourcing](skills/component-sourcing/SKILL.md)，核对 PCB 布局用 [pcb-layout-review](skills/pcb-layout-review/SKILL.md)。涉及多个专项时，用 `$hardware` 说明目标、现有工件、平台和期望产物。

| 可以这样问 | 这次会交付什么 |
| --- | --- |
| 「用 `$hardware` 画一张 RC 低通示意图，给 SVG。」 | Schemdraw 源码和 SVG。需要可编辑的工程原理图时，写明 Altium、EasyEDA Pro 或 KiCad。 |
| 「只读核对这份保存的 Altium 工程，按页列出器件数。」 | 工程成员、保存态的器件明细和无法解析的文件。若还需要未保存的编辑内容，再申请现场读取。 |
| 「审这路 ADC 前端，把需要验证的条件和资料页写出来。」 | 与器件和工况对应的规则、文档版次、物理页或印刷页，以及待计算或待测的项目。 |
| 「优先在我给的标准阻容索引里找料，缺项再查公开来源。」 | 符合规格的候选、缺证据的字段，以及适用的商品页或原厂资料。为工程确认选用时，可从已核对数据生成 AD 选型表。 |
| 「这份 BOM 只转档案 CSV，已有料号原样保留。」 | 按指定模板生成 CSV，读回核对列、位号、数量和料号。 |
| 「看这份 KiCad DRC JSON，把未连接项、禁用规则和覆盖缺口列出来。」 | 已有报告的只读汇总，附报告来源、版本和 SHA-256。 |
| 「投板前核对这版 BOM 和贴装坐标，TP1 不贴。」 | 缺贴、多贴、重复位号和坐标字段问题，以及两份输入的 SHA-256。 |
| 「先识别这个嵌入式工程的工具链，给出构建和 J-Link 烧录的步骤预览。」 | 工具链、目标配置、拟执行步骤与缺项。实际构建、烧录和复位由对应专项按授权执行。 |
| 「核对这份外壳 STEP 的尺寸和工艺要求，先准备 Fictiv 报价用的资料。」 | 本地文件预检和已知的材料、工艺、数量及公差。供应商的 DFM 反馈需要按授权上传后取得。 |
| 「用这份限值判定台架结果，标出超限、缺项和单位错误。」 | 对照板号、硬件版次、固件哈希和单位的逐项核对结果。 |

单项任务交付所问结果即结束。整板任务才需要把接口、版本和验证结果交给后续专项。

## 架构与分工

![硬件技能包架构。路由按平台和权限选择专项，从规则与器件事实、工程验算或保存态后端取得证据，交付单项答复或正式审查记录。](docs/architecture/hardware-design-skills.png)

- `$hardware` 根据目标、已有工件、EDA 平台和授权选择专项与交付停点。
- `hardware-solution` 协调整板的供电、引脚、通信、机械和固件接口。
- `manage-pcba-program` 管理 PCBA 阶段、工件版本与重验范围，阶段状态为 `PASS`、`BLOCKED` 或 `USER_REVIEW`。
- `hardware-design-review` 汇总工程证据，给出 `Go`、`Hold` 或 `No-Go`，附判定范围与待核项。

### 各模块怎么配合

| 模块 | 接收什么，交付什么 |
| --- | --- |
| [任务路由与权限](docs/architecture-guide.md#任务路由与权限) | 根据工件状态和真实工具动作选入口。执行前检查许可，在用户要求的交付点停止。 |
| [需求与整板协调](docs/architecture-guide.md#需求与整板协调) | 把目标和参考工程转成可测要求与接口约束，交电路、PCB、固件和测试。 |
| [工程知识与综合评审](docs/architecture-guide.md#工程知识与综合评审) | 查适用规则和资料页，按 [关键工况](skills/hardware/references/engineering-verification.md) 收集证据，给出通过、待验证或阻塞项。 |
| [器件选型与 BOM](docs/architecture-guide.md#器件选型与-bom) | 用规格、订购 MPN 和渠道编号核对器件。把原厂脚位、封装和资格结果交给库、BOM 或制造。 |
| [原理图、工程库与 PCB](docs/architecture-guide.md#原理图工程库与-pcb) | 按 Altium、EasyEDA Pro 或 KiCad 选择入口。交付可编辑工件，或给现有工件的只读检查结果。 |
| [电路仿真](docs/architecture-guide.md#电路仿真) | 对指定模型、输入和工况运行求解，给波形及量测。结果回到电路设计或评审。 |
| [机械与装配](docs/architecture-guide.md#机械与装配) | 用板框、孔位和结构约束做板壳匹配，交 CAD 和尺寸证据，回传 PCB 修改项。 |
| [固件与台架](docs/architecture-guide.md#固件与台架) | 接口约定进入固件构建，镜像绑定板号和测量结果。故障回到电路、固件或配置的源头排查。 |
| [制造包与供应商](docs/architecture-guide.md#制造包与供应商) | 冻结同版 Gerber、钻孔、BOM、CPL 及清单。按具体授权处理外部预览、报价和订单。 |

模块图给出每一步的输入、分支和交接点。按具体技能查职责时，可以直接打开 [48 项技能索引](docs/skill-catalog.md)。图标来自 [Lucide](https://lucide.dev/)。

### 以一块传感器采集板为例

1. **需求与接口**。确定采集范围、误差预算、供电和通信接口，记录各项验收条件。
2. **选料与电路**。从原厂资料核对 MPN、封装、脚位和采样工况，交付原理图、关键网约束及所需的仿真结果。
3. **PCB、机械与固件并行**。共用同一版板级接口约定，同步板框、孔位和连接器装配空间。
4. **首板联调**。用板号、硬件版次和固件哈希绑定日志与测量。异常先区分供电、模拟前端、采样配置和测量条件，再由对应专项在同一工况下复验。
5. **制造冻结**。绑定同版 PCB、BOM、CPL、CAM 读回与装配证据。贴装预览方向有误时，沿库件、板上放置和 CPL 导出追查，修正源头后重新核对受影响的工件。

## 48 项技能速览

下表可按工程阶段定位技能。每项的输入、交付物和上下游交接约定见[完整技能目录](docs/skill-catalog.md)。

| 工程阶段 | 技能入口 |
| --- | --- |
| 路由、需求与项目协作 | `hardware`、`plan-electronic-product`、`hardware-project-library`、`hardware-solution`、`manage-pcba-program` |
| 电路图、电气设计与综合审查 | `draw-schemdraw-circuit`、`design-and-review-circuit`、`schematic-analyzer`、`schematic-humanizer`、`hardware-design-review` |
| 原生 EDA、元件库与 PCB | `altium-library`、`altium-schematic-review`、`altium-pcb-review`、`easyeda-agent`、`autodesign`、`pcb-layout-review` |
| 器件选型、Datasheet 与 BOM | `component-sourcing`、`ee-datasheet-master`、`bom-material-archive`、`qualify-pcba-sourcing` |
| 机械、制造包与供应商 | `lab-hardware-cad`、`release-pcba-fabrication`、`operate-jlcpcb-order`、`fictiv` |
| 固件设计与工具链路由 | `embedded-firmware-design`、`embed-ai-tool`、`workflow` |
| 固件构建 | `build-keil`、`build-iar`、`build-idf`、`build-cmake`、`build-makefile`、`build-platformio` |
| 固件烧录 | `flash-keil`、`flash-idf`、`flash-openocd`、`flash-jlink`、`flash-platformio` |
| 固件与实时故障调试 | `debug-gdb-openocd`、`debug-jlink`、`debug-platformio`、`rtos-debug` |
| 台架、通信协议与测量 | `serial-monitor`、`serial-shell`、`can-debug`、`modbus-debug`、`logic-analyzer`、`visa-debug` |

原生 EDA 按工程格式选择 Altium Designer、嘉立创 EDA 专业版（EasyEDA Pro）或 KiCad。Cadence OrCAD Capture XML 和 Allegro 网表组合可用于只读提取电路结构。具体需要的 CLI、连接器及版本见[运行依赖](docs/backends.md)。

## 工程知识、计算与正式审查

### 按工况找判据

从 11 个工程域进入相应专题。随包的 96 条审查规则按 9 类主题组织，保留原件定位。手册索引另有 175 个来源编号，可查询版次、引用点及访问范围。若有自己的全文资料库，可用 `--library` 接入，按文档号、印刷页和 OCR 结果定位到原页。[工程域索引](skills/hardware/references/lifecycle-domain-index.md) · [来源索引](skills/hardware/references/source-index.md) · [自有资料库接入](skills/hardware/references/engineering-knowledge.md)

```powershell
python -X utf8 skills/hardware/scripts/knowledge.py sources AN2867 --limit 3
python -X utf8 skills/hardware/scripts/knowledge.py rules --domain PCB与EMC --summary
```

### 选择可复算的验算模型

| 入口 | 可核对的工程问题 |
| --- | --- |
| `engineering_checks.py evaluate` | 提供 I²C 上拉窗口、分压最坏情况、热态铜损、测量保护带、钢网面积比、零失效置信上限、公差链及二端口 S 参数采样无源性八个模型。[输入参数与算例](skills/hardware/references/model-checks.md) |
| `engineering_checks.py adc-settling` / `pdn-target` | 估算 SAR ADC 一阶建立误差，或按目标阻抗核对 PDN 扫频样本。[工程预算](skills/hardware/references/engineering-budgets.md) |
| `engineering_validation.py` | 支持单项区间限值比较、故障检测覆盖率区间、RS-485 支线筛查、稳态结温及圆孔最小环宽。[工程核验与调用示例](skills/hardware/references/engineering-verification.md) |

例如核对 2 kΩ 上拉时，先用供电、电容、上升时间与器件灌电流算可用阻值窗，再比较实物公差。三个入口共提供 **15 种计算或核验方式**，使用 Python 标准库。退出码 `0` 表示已得到所求计算结果或满足本次核验条件，`1` 表示已证越界，`2` 表示待判或输入无效。保守区间只在部分角点越界时，需查这些角点能否实际达到。

### 读回正式审查证据

在已有 KiCad 报告、制造清单和台架记录的检查命令上加 `--formal`，输出版本化证据外壳。记录包含工件 SHA-256、执行状态、修改结果、验证结论及已查和跳过项。KiCad 报告的零发现仅覆盖该报告所记录的检查范围。[证据字段与后端状态](skills/hardware/references/evidence-and-backends.md)

```powershell
python -X utf8 skills/hardware/scripts/hardware_tool.py kicad-report-check board-drc.json --kind drc --formal
```

从保存态工件重新取证时，可以在隔离输出目录运行 KiCad ERC/DRC，使用 ngspice 执行受控网表并读回命名量测，或使用 Gerbonara 独立读回 Gerber 和 Excellon 的图层几何及孔槽。正式审查保留版次、实际运行条件、结果与缺项。[KiCad 原生检查](skills/pcb-layout-review/references/kicad-native-checks.md) · [SPICE 量测](skills/design-and-review-circuit/references/spice-readback.md) · [CAM 读回](skills/release-pcba-fabrication/references/cam-readback.md)

## 固定离线工具速查

从仓库根目录运行。预检示例中的 `bom.csv` 和输出目录按项目替换。

```powershell
python -X utf8 skills/hardware/scripts/hardware_tool.py list --json
python -X utf8 skills/hardware/scripts/hardware_tool.py --plan bom-archive bom.csv --output out/archive.csv
```

| 子命令 | 权限级别 | 输出 |
| --- | --- | --- |
| `ad-saved` | L0 | 读取保存的 `.PrjPcb`、`.SchDoc` 或 `.PcbDoc`，给工程成员或对象数据。需要 `altium-monkey`。 |
| `bom-archive` | L0 / L2 | 预检 BOM 及映射。指定 `--output` 时生成档案 CSV 并读回。 |
| `selection-export` | L2 | 从已核对 JSON 生成 AD HTML 或按需生成 Excel。补 Excel 可用 `--xlsx-only`。 |
| `sourcing-lock-check` | L0 | 核对资格表字段、数量、费用及已记录证据的时效。 |
| `kicad-report-check` | L0 | 读取现有 KiCad 9/10 ERC 或 DRC JSON，列出违规、排除、禁用规则与覆盖范围。支持 `--formal`。 |
| `assembly-check` | L0 | 对照同版 BOM 与 CPL，核对位号、DNP、板面、坐标格式和单位。 |
| `release-check` | L0 | 校验冻结制造包清单、版次、尺寸及 SHA-256，并对所列制造 BOM/CPL 重新做装配数据核对。支持 `--formal`。 |
| `bench-check` | L0 | 按输入限值核验台架测量，标出超限、记录无效与缺项。支持 `--formal`。 |

器件专项另有本地阻容筛选、批量查料和按同约束分组的入口。[固定命令用法](skills/hardware/references/local-tools.md) · [器件批查与续跑](skills/component-sourcing/references/batch-lookup.md)

## 权限怎么划分

| 级别 | 典型动作 |
| --- | --- |
| L0 离线读取 | 读保存版工程、库、报告和本地测量数据。 |
| L1 定向只读 | 读已获准的活动文档，或查询公开料价。审查保存态时，转到活动工程需要单独核对许可。 |
| L2 有界本地操作 | 写指定副本、生成本地工件、构建、后台仿真，或不保存设计源的非模态编译。 |
| L3 原工程、前台、设备与外发 | 原工程写入、模态 DRC、桌面操作、烧录、主动发帧、仪器输出、上传、下单和付款。 |

一次调用的等级取其中影响最大的动作。Altium 从离线读取升级到现场桥接，再升级到桌面操作时，分别核对授权。工程和 3D 文件默认留在本机，外发需要针对文件和接收方批准。 [权限细则](skills/hardware/references/permission-gates.md)

## 仓库结构

| 路径 | 内容 |
| --- | --- |
| `skills/` | 48 个平级技能。每个目录从 `SKILL.md` 进入，所需脚本、参考资料及夹具就近存放。 |
| `docs/` | 总图、模块流程图、技能目录及可选运行依赖。 |
| `scripts/` | 离线安装、技能包校验与发布扫描。 |
| `tests/` | 共享离线回归、合成夹具与可选原生工具测试。原理图分析和工程库专项另有自己的测试目录。 |

## 验证与测试

Windows 和 Linux CI 检查技能元数据、相对链接、Python 语法、离线安装、固定工具和可发布内容。项目的原生 EDA、供应商和实体台架结果以实际工程的运行记录为准。

```powershell
python -X utf8 -m pip install -r requirements-dev.txt
python -X utf8 scripts/validate_bundle.py
python -X utf8 scripts/check_publication.py --tree HEAD
python -X utf8 -m pytest -ra tests skills/schematic-analyzer/tests skills/hardware-project-library/tests
```

### 上游原板夹具

原理图专项的层级、查询、缓存和运行时配置测试可使用临时生成的 KiCad 工程。需要核对上游原板的 13 项回归另用 Denali（11 项）和 E1005_v01（2 项）。例如 Denali 要能在 `RK3576.kicad_sch` 的工程层级中读到 U36 的完整料号和 `/FPCIO/FPC_I2C_SCL`。E1005 用例核对层级标签、页名和全部匹配项。官方 Sticky PDF 和 STEP 可协助识别板卡，运行这些用例还需要对应版次的原生 KiCad 工程。[上游固定提交](https://github.com/Seeed-Studio/ai-skills/tree/32a1f21b834bcb08bd273e155d70257dd3d5dbef) · [Sticky 官方硬件资料](https://www.seeedstudio.com/sticky/docs/zh/device-guide/hardware-overview/)

取得两套原工程后，将含子图的完整目录分别放在同一夹具根的 `denali/` 和 `E1005_v01/` 下，让 `kicad-cli` 在 PATH 中可用，然后运行专项。显式指定的夹具路径出错时测试会报错。默认环境缺原板时，pytest 逐项显示跳过原因。

```powershell
$env:SCHEMATIC_ANALYZER_TEST_DATA = (Resolve-Path ./board-fixtures).Path
python -X utf8 -m pytest -ra skills/schematic-analyzer/tests
```

## 许可

自有内容采用 [MIT](LICENSE)。随包第三方文件保留各自版权和许可。 [来源与许可](THIRD_PARTY_NOTICES.md)
