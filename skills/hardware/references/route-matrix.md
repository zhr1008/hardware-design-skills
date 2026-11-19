# 硬件专项分流与交接

按用户要做的动作、实际工件、目标平台和交付终点选取当前专项。直接执行单项任务时，加载这一项所需的正文和适用工具签名。跨软硬件的整板交付用 `hardware-solution` 协调，PCB/PCBA 的阶段和工件状态用 `manage-pcba-program` 管理。跨阶段时携带已验证的结果和未关闭的问题，接手方核对当前版本后继续。操作授权见 [权限与停止点](permission-gates.md)。

## 同名技能的来源

依次选用用户精确点名的技能路径或带命名空间的入口、项目已明确采用的来源、当前可用的随包技能。用户级安装时通常位于 `.codex/skills`。各来源还须满足当前的启用状态、调用策略和依赖。同一专项一次只读所选来源的正文、脚本和参考，固定批处理只调用随包实现。插件另有特定宿主的 `PORTABILITY.md`。`electronic-product-planner` 0.3.0 的 `hardware-solution` 仍写旧名 `szlcsc`，涉及器件选型时向当前 `component-sourcing` 或本轮实际暴露的 `components` 工具交接，`szlcsc_*` 是 `components` 仍可使用的工具名前缀，具体方法以当前签名为准。

本地来源无法使用或缺少适配能力时，才选当前可提供同等验收证据的插件或普通工具，记录缺口和新入口。用户或项目已固定来源时，先说明该来源的实际障碍及可行替代，再按其约束决定是否切换。单次工具失败先诊断原因和会话状态。

| 本机 `.codex/skills` | `electronic-product-planner` 0.3.0 的精确入口 |
| --- | --- |
| `design-and-review-circuit` | `electronic-product-planner:design-and-review-circuit` |
| `ee-datasheet-master` | `electronic-product-planner:ee-datasheet-master` |
| `embedded-firmware-design` | `electronic-product-planner:embedded-firmware-design` |
| `hardware-project-library` | `electronic-product-planner:hardware-project-library` |
| `hardware-solution` | `electronic-product-planner:hardware-solution` |
| `manage-pcba-program` | `electronic-product-planner:manage-pcba-program` |
| `operate-jlcpcb-order` | `electronic-product-planner:operate-jlcpcb-order` |
| `pcb-layout-review` | `electronic-product-planner:pcb-layout-review` |
| `plan-electronic-product` | `electronic-product-planner:plan-electronic-product` |
| `qualify-pcba-sourcing` | `electronic-product-planner:qualify-pcba-sourcing` |
| `release-pcba-fabrication` | `electronic-product-planner:release-pcba-fabrication` |
| `schematic-humanizer` | `electronic-product-planner:schematic-humanizer` |

## 按工程平台选执行入口

| 对象与状态 | 推荐入口和检查点 |
| --- | --- |
| 本地手册、标准、教材或既有逐页 OCR | [工程资料检索](engineering-knowledge.md) 先核版本再定位正文；使用本地 OCR 时报告物理页、印刷页和覆盖范围。以相同版次的原页核对文字、公式及工况。 |
| 确定电路、PCB 或综合审查的核验依据 | [设计与审查规则](design-review-basis.md) 按对象、工况和版次选规则，核对引文后交专项落实。明确记录适用范围、证据与判定。 |
| AD 已保存的 `.SchLib` / `.PcbLib` | `altium-library` 配 `mcp__altium_offline_library__*`，如 `read_schlib`、`validate_library` 和 `diff_libraries`，读取库条目、引脚/焊盘和图元，按需做校验、渲染、前后差异。写入使用授权副本和工具的 `allowed_paths`，从磁盘读回。原厂脚位、尺寸和封装变体是库验收依据。已有库的批量物料参数整理按 `component-sourcing` 的实际入口处理。 |
| AD 已保存的 `.PrjPcb` / `.SchDoc` / `.PcbDoc` | [`ad-saved`](local-tools.md) 按工程清单批查或读取单个文档，盘点成员、位号、原理图引脚数量/封装引用和板上器件/焊盘概要。疑似悬空脚、封装链接等交 `altium-schematic-review` 初筛并对照原厂手册。需要编译层级、多分件或当前编辑态证据时按授权切到 AD 现场入口，保留已读取范围和缺口。 |
| AD 活动工程的连续操作 | 选 `mcp__eda_agent__*` 做工程身份与文档上下文确认、跨文档快照、原生编译/检查、相关对象迭代和导出。按本轮签名用 `app_context` 确认已连接项目和文档，再按需选择 `design_review_snapshot`、`proj_compile` 等，检查响应中的实际执行和原生结果。 |
| AD 现场定向查询、批处理或 OutJob | 可选 `mcp__altium__*` 执行已明确的页/板/网络查询、原生 ERC/DRC、符号/封装批操作或指定 OutJob 容器，如 `get_schematic_data`、`build_schematic`、`run_output_jobs`。按实际签名与 `eda_agent` 择一承接同一组写入、保存和回读，留存输入与输出身份。 |
| EasyEDA Pro | `easyeda-agent` 配当前可用的 `easyeda` CLI、daemon 和 Pro 宿主连接器。确认目标为专业版原生文档和正确项目/页，使用当前 typed 入口，以 `saved:true`、重载和新读回验收。若实际有匹配的设计执行会话，再按需选择 `autodesign`。标准版公开资产用于参考时标明来源和版本。 |
| KiCad | 已有原生 ERC/DRC JSON 用 [`kicad-report-check`](local-tools.md) 读取，按报告工件、版本和覆盖范围写结论。需新结果时才用对应工程版本的 `kicad-cli` 运行，经授权向本地输出报告。编辑按实际可用的原生/IPC 路径或 `text-to-cad:pcb`，使用可能升级格式的编辑器前核对版本和副本。`eda_agent` 须证实连接正确的 KiCad 后端且有匹配签名。 |

切换 AD 路径前，先从已授权来源核对项目路径、落盘版本和前一动作结果。取得现场许可后，再读取活动文档和未保存状态。切换两套桥前应确认前一批写入、保存和读回已完成或已回退。必要时用用户授权的保存、重开或新读回建立基线，两个视图有差异时标清各自能支持的结论。现场结果核对实际执行标志、报告来源和规则，零违规须有规则实际运行的证据。跨平台转换是独立任务，需按目标格式重新核对层级、脚网、封装和板层。

## 原理图、PCB 与后续停点

| 目标 | 主专项与交付 |
| --- | --- |
| 从受支持的 KiCad/Cadence 输入提取层级、脚网、电源树或信号链 | `schematic-analyzer`，按受支持的源文件或导出取结构证据，标明推断。 |
| 对 AD 原理图做只读审查 | `altium-schematic-review`，定位页、位号、引脚、网络及封装链接，逐脚对照原厂资料区分真实问题和初筛误报。 |
| 电路设计、电气审查或局部电气修改 | `design-and-review-circuit`，核对工况、计算、时序和故障状态。只读终点交问题和证据。要求改动时，编辑权威原理图，保存重开复核脚网、受影响约束和适用的 ERC 或仿真。 |
| 改善原理图排版与可读性 | `schematic-humanizer`，先确认原生工具支持要调整的对象，交付前后整页图与脚网等价检查。 |
| 只读检查 AD 实际板、规则、回流与层叠 | `altium-pcb-review`，交工程/板版次、原生连接证据、适用规则和按层/位号/网名定位的问题。 |
| 布局布线、派生改板与关键网约束 | `pcb-layout-review`，由实际网表、叠层、机械和回流约束起步，按授权修改并交原生板、新读回及受影响的 DRC/未连接证据。 |
| 跨原理图、PCB、BOM、制造或实测的评审 | `hardware-design-review`，按对象区分综合评审、发板门禁和故障 RCA。门禁交固定版本的 `Go/Hold/No-Go`、适用判据、缺口和关闭条件。 |
| 核对现成 BOM 和 CPL | [`assembly-check`](local-tools.md)，在指定变体对照双方位号和装配字段，按实际缺漏和冲突交付核对结果。 |
| 冻结版本的制造包 | `release-pcba-fabrication`，交同版 Gerber/钻孔、通过装配数据核对的 BOM/CPL、装配资料、独立 CAM 检查和版本/hash 清单。 |
| 嘉立创报价和实际导入复核 | `operate-jlcpcb-order`，根据用户授权的终点核对板选项、物料匹配、贴装预览及指定数量的报价，记录导入差异和结果。 |

只读审查停在可定位的发现和证据，局部修改停在指定源的保存、回读与对应复核，综合门禁停在该版结论和关闭条件，制造包停在可校验的本地交付，报价停在授权的报价或预览。按用户要求的停点选择当前动作，已有授权覆盖的后续阶段可接着推进。制造门禁是工程证据结论，工厂端的实际操作按 [权限与停止点](permission-gates.md) 判断。

## 其他专项的主入口

| 任务 | 先用 |
| --- | --- |
| 产品需求与可测设计输入／已有工程与参考复用 | `plan-electronic-product` ／ `hardware-project-library`。整板跨专业交付用 `hardware-solution`。 |
| 查器件、核对已知型号、比较指定条目、查库存或数量价 | 有用户提供的标准阻容索引时先做 [离线筛选](../../component-sourcing/references/sourcing-queries.md#标准库优先与外部检索)，只补证据缺口。实时库存、价和采购档位用对应渠道。默认以所问事实或候选在正文结束。 |
| 为工程选用或替换器件，包括一个位号 | `component-sourcing` 按适用的本地证据、原厂和渠道核对条件。已有选型仅收窄或修改条件时复用上轮筛选状态。按 [导出流程](../../component-sourcing/references/ad-selection-export.md) 用已核验数据生成默认 HTML，明示格式优先。追加 Excel 时复用已交付的数据。 |
| 逐位号 BOM 资格、替代适用性和供货证据 | `qualify-pcba-sourcing` 负责资格结论，按需从 `component-sourcing` 取得精确身份及渠道证据。 |
| 将电子 BOM 转换成物料档案 CSV，或补齐档案的渠道料号 | [bom-material-archive](../../bom-material-archive/SKILL.md) 保留模板字段、层级、位号及数量，必要时定向查料。纯 CSV 以已提供 BOM 和模板为输入，停在 CSV 读回。 |
| PCBA 进度、版本、证据和变更传播 | `manage-pcba-program`。 |
| 可编辑教程或解释用电路图／可执行电路仿真 | `draw-schemdraw-circuit` ／ `design-and-review-circuit` 配用户指定且已验证的求解器。原生 Multisim 工程及实验用 `multisim`。离线网表仿真、扫参与波形分析可用 `ltspice-mcp`，核对本机启用的后台引擎和任务授权的输入输出路径。 |
| 固件设计、BSP 和驱动／单次构建、烧录、调试 | `embedded-firmware-design` ／ 工程匹配的 `build-*`、`flash-*`、`debug-*` 专项。需要识别工程或组织这些运行环节时用 `embed-ai-tool`。 |
| 台架、总线、仪器／已有测试数据 | 优先处理已有数据。已有契约匹配的测量 CSV 和限值 JSON 时用 [`bench-check`](local-tools.md)。日志、波形和其他数据按格式用 `exploratory-data-analysis`、`matlab` 或适用的不确定度/统计专项。需新取证再按授权选串口、CAN/Modbus、逻辑分析仪或 VISA 专项。 |
| 板框、外壳、夹具或工程图／文档和实验记录 | 工件匹配的 `text-to-cad` 专项或 `lab-hardware-cad` ／ 项目现有交接格式对应的文档或表格入口。 |
| SOLIDWORKS 原生装配、零件与 COM 脚本 | 优先使用本机 SDK、模型及 COM。`swapi-pilot` 的本机入口仅转发公开 API 标识，模板和脚本在本机生成与审查。运行 COM 前核对实例、文档身份、文件范围及前台副作用。可能影响前台或外发 3D 文件时，分别先获批。 |

## 跨专项移交与变更回流

涉及信号完整性、EMC、热、绝缘、DFM／DFT 或器件资格的交接，按 [工程核验](engineering-verification.md) 附限值来源、适用工况、项目决策规则、实际证据和未验证项。复算报告随输入工程和版次保存。

移交记录至少带上工件路径、对象位置和版次，说明证据的来源、工况和验证范围，给出接手方要执行的检查。上游变更后标出已失效的证据及对应的下游结论。先由拥有权威源的专项修复，再更新受影响的交接物、重跑相关验证，并把新结果及剩余缺口回写到项目状态。保留旧证据供追溯。

禁止在下游单点掩盖源头错误。厂商网页上的临时坐标调整、BOM 文本替换和联调临时改脚可以帮助定位。正式放行须使用更新后的权威源及重新核验的对应工件。若差异仅来自厂商的坐标解释，记录可复现的厂商映射后重验该厂商的实际预览。

| 移交 | 最小内容与接手检查 |
| --- | --- |
| 器件与手册 → 库、BOM、原理图 | 位号/变体、厂家与完整 MPN（含订购后缀）、原厂 PDF 修订/页码、引脚图、封装图与推荐焊盘、脚位到 Pad 的映射、关键额定值与工况、DNP、渠道料号和供货证据。库按封装/极性/几何复核，BOM 按资格和映射锁定。 |
| 原理图 → PCB | 工程和板版次、已保存/未保存状态、编译网表或离线证据范围、ERC/豁免、关键网名与约束、叠层与机械要求。涉及 ADC/PDN 时附 [工程预算](engineering-budgets.md)、工况、测点与待验证项。PCB 接手后检查同步、实连接、规则与受影响的关键网。 |
| 软硬接口 → 固件与联调 | 板版次、接口规格和引脚映射，电平/极性、复位默认态、时序/速率、故障安全状态、已知变体与验收工况。固件侧交 SDK/配置、镜像版本/摘要和运行记录，联调侧按同版板和镜像对照实测。 |
| PCB 与放行 → 制造包 → 供应商 | 冻结版、放行依据、清单/hash、Gerber/钻孔、BOM/CPL、装配图与变体、层叠/工艺、坐标原点/单位/角度和拼板约定。供应商侧按当前导入的板边、层、钻孔、料号和正反面预览复核。 |
| 台架和仿真 → 数据分析 → 电路/固件 | 原始数据/抓包、板号及固件构建标识、接线、仪器和采样配置、触发/时间基准、单位/量程/探头、工况和样本关系、预期阈值。仿真再带模型来源、求解器和量测窗口。回交可追溯的图表或指标、支持与反驳的证据和复测条件。 |

| 发现 | 回源修复、失效与重验 |
| --- | --- |
| 工厂预览的贴装方向错 | 比对原厂 pin 1/极性、封装朝向及 CPL 的角度、原点、层面，定位到封装/PCB、导出配置或厂商解释。回到库、版图或制造发布修正源。偏差来自厂商解释时，把确认的转换约定登记到可复现的交接配置。将依赖旧坐标的装配检查和预览结论标记失效，重出受影响的 CPL、装配图或制造文件，更新清单/hash 并回交制造与供应商专项。重验双面预览，选项或成本受到影响时同步复核报价。 |
| 候选替代料的引脚或封装变了 | 回到原厂资料和 `qualify-pcba-sourcing` 重新核定。采用替代料时同步更新 `sourcing-lock.csv`、库和受影响的原理图/PCB。旧资格/映射和依赖该映射的 DRC/装配结论随之失效。重验 pin→Pad、网络及规则，更新受影响的 BOM/CPL 或制造文件后回交供应商核对匹配和贴装，接口行为受影响时回传固件和联调复验。 |
| 联调发现要改管脚 | 将原始连通/时序证据回传电路与固件，更新接口合同、权威原理图及 BSP/引脚配置；PCB 连接改变时从原理图同步。旧映射、受影响网的检查和旧镜像上的联调结论失效，按影响重验 ERC、脚网/DRC、构建与新板/镜像匹配的联调工况。已冻结制造数据受影响时重新走对应放行和交接。 |

### 跨域故障 RCA

1. 用 `hardware-design-review` 把复现工况、板版次、固件/配置和现象写清。提出可区分的假设（hypotheses），为每个假设注明应出现的特征和能推翻它的观察。例如总线超时可能出自供电压降、物理层错误或固件调度，分别在复位/电源、总线错误帧及任务时间戳上找证据。
2. 优先利用已有波形或日志。需新取证时按权限选 `serial-monitor`、`can-debug`、`modbus-debug`、`logic-analyzer` 或 `visa-debug`，根据目标和 [权限与停止点](permission-gates.md) 区分读取、监听及会改变设备状态的操作。采集同一触发条件下可关联的电气波形、协议记录和固件日志，保留原始数据及仪器配置。
3. 按台架数据的时钟、触发、工况、单位及样本关系对齐，交测试数据分析专项检查缺失、误差与可重复性。用结果对照各假设的预期和反证，记录支持范围、仍可解释现象的其他假设以及未测条件。
4. 将定位到的电路、版图或固件问题交给拥有源的专项按授权处理。更新相应合同/工件，重验受影响的连接、构建或制造证据。在同一工况复现旧故障并对比新版本的结果，按实际风险补测相关边界条件。原始数据和版本随结论回交，缺少必要取证时保留待验证状态。
