# 技能目录与交接关系

本表覆盖公开包中的 48 个技能。每项都可以单独调用。整板任务用 [hardware-solution](../skills/hardware-solution/SKILL.md) 保持系统接口一致，用 [manage-pcba-program](../skills/manage-pcba-program/SKILL.md) 记录 PCBA 阶段状态，实际产物由对应专项完成。

输入应绑定目标工件、工程版次和所需证据。交付时记录来源、工况、核对结果、缺项和停点。现场、写入、设备及外发操作按动作和参数核对授权。软件、SDK、MCP、CLI 和设备由使用环境按需提供。仿真按目标求解器和实际模型接入，归电路设计和复核流程。 [权限门禁](../skills/hardware/references/permission-gates.md) · [运行依赖](backends.md)

## 路由、需求与阶段协作

| 技能 | 用途 | 输入与交付终点 | 交给谁或从谁接收 |
| --- | --- | --- | --- |
| [`hardware`](../skills/hardware/SKILL.md) | 主持规划、设计、改版和审查 | 从用户要求和工件建立可测目标，先查本地依据，再比较方案或评估工程 | 带着依据和判据调用专项，读回证据、处理反例并在目标停点交付 |
| [`plan-electronic-product`](../skills/plan-electronic-product/SKILL.md) | 把产品想法和行为描述转成工程要求 | 接收目标、使用场景及商业和机械约束，交付 `product-brief.yaml` 与 `architecture.md` | 从参考库取适用资料，把供电、引脚、行为和可测条件交给系统、电路及固件设计 |
| [`hardware-project-library`](../skills/hardware-project-library/SKILL.md) | 查找、评估和管理可复用参考工程 | 输入要复用的模块或指定资料，交付带来源、版本、适用边界和验证状态的参考记录 | 为需求、整板、电路和 PCB 提供有出处的基线，变更在派生工程中验证 |
| [`hardware-solution`](../skills/hardware-solution/SKILL.md) | 统筹整板开发、软硬协同和改版 | 输入需求或既有工程，按目标推进到设计文件、固件与复核记录 | 跨阶段保持供电、引脚、时序与故障接口一致，把实现和验收交给相应站点 |
| [`manage-pcba-program`](../skills/manage-pcba-program/SKILL.md) | 管理从设计到复核订单的阶段记录 | 输入已有工件、评审、批准和变更，汇总为 `.pcba-workflow/` 阶段记录和下一步 | 接收器件、布局、制造等专项证据，按 `PASS`、`BLOCKED`、`USER_REVIEW` 管理阶段 |

## 电路图、电气设计与综合审查

| 技能 | 用途 | 输入与交付终点 | 交给谁或从谁接收 |
| --- | --- | --- | --- |
| [`draw-schemdraw-circuit`](../skills/draw-schemdraw-circuit/SKILL.md) | 为明确拓扑生成可读电路图 | 输入拓扑、元件和连线要求，通过 Schemdraw 交付 Python 源码和经检查的 SVG 或 PNG | 教程、说明和沟通可在图片结束。需原生 EDA 或仿真时沿用拓扑交给对应流程 |
| [`design-and-review-circuit`](../skills/design-and-review-circuit/SKILL.md) | 做电气设计、专项审查和授权内更正 | 输入工程要求、原理图或网表，交付器件、连接、计算和工况证据。实现任务交付目标 EDA 的原生源及读回 | 使用 Datasheet 与器件证据，把核对后的脚网和布局约束交给 PCB 与固件。需要波形时通过配置好的求解器验证模型 |
| [`schematic-analyzer`](../skills/schematic-analyzer/SKILL.md) | 从原理图提取器件、网络、总线与电源树 | 输入受支持的 KiCad 或 Cadence 工程材料，交付网络、器件角色、层级和覆盖证据 | 为电气审查、BSP 和测试准备结构事实，器件规格交由原厂资料核实 |
| [`schematic-humanizer`](../skills/schematic-humanizer/SKILL.md) | 重排原理图，让功能分组和局部连线可读 | 以原生图和已记录脚网为基线，交付重排结果、视觉检查和连接对比 | 电气内容沿用电路设计结论，结果可作为 PCB 分组依据。实际编辑使用选定 EDA 适配器 |
| [`hardware-design-review`](../skills/hardware-design-review/SKILL.md) | 综合评审、冻结判定和板级故障分析 | 对齐同版电路、PCB、BOM、固件、仿真与实测，交付 `Go`、`Hold` 或 `No-Go` 与关闭证据 | 接收各专题的发现，按根因把问题退回电路、布局、器件或固件。冻结结果供发布流程使用 |

## 原生 EDA、元件库与 PCB

| 技能 | 用途 | 输入与交付终点 | 交给谁或从谁接收 |
| --- | --- | --- | --- |
| [`altium-library`](../skills/altium-library/SKILL.md) | 制作和验证 Altium 符号及封装 | 输入原厂数据手册、机械图、现有库和目标尺寸，交付 `.SchLib`、`.PcbLib` 或用保存副本取得的校验记录 | 核对引脚、焊盘、3D 与机械证据。可按任务接入独立离线库 MCP 或 `altium-monkey` |
| [`altium-schematic-review`](../skills/altium-schematic-review/SKILL.md) | 审查保存的 Altium 原理图与项目成员 | 输入 `.SchDoc` 或 `.PrjPcb`，列成员、脚网、封装引用和候选问题，按 Datasheet 判读缺口 | 批查与静态解析优先。需要当前会话证据时按门禁接入，电气修复交给电路专项 |
| [`altium-pcb-review`](../skills/altium-pcb-review/SKILL.md) | 只读核对 Altium 板级连接、规则和 DFM | 输入保存版 `.PcbDoc` 或获准现场板及报告，交付定位到层、网络、器件或规则的发现与复核路径 | 可用原理图批查补上下文。实际板级修复进入 `pcb-layout-review` 后按新版本读回 |
| [`easyeda-agent`](../skills/easyeda-agent/SKILL.md) | 编辑嘉立创 EDA 专业版原理图和 PCB | 输入需求、真实器件数据与工程，通过兼容的 EasyEDA CLI、daemon 与连接器交付已保存文档及连接、几何、DRC 证据 | 跨阶段约束来自电路设计和选型。完整项目按 `hardware-solution` 向 PCB、固件及制造交接 |
| [`autodesign`](../skills/autodesign/SKILL.md) | 按用户请求运行获准的 EDA 设计会话 | 输入目标平台、要求、授权和原生工件，核对当前工具后按实际支持的步骤推进并复核持久化结果 | 先由 `hardware-solution` 定位阶段，使用目标 EDA 的专项和已配置宿主工具完成动作 |
| [`pcb-layout-review`](../skills/pcb-layout-review/SKILL.md) | 审查、收尾或迁移 PCB 布局布线，也可承接新板实现 | 输入已验证脚网、封装、板框、机械与制造约束，交付原生板或布局问题表，附连通、几何和规则证据 | 接收电路与器件封装映射。回流引脚和电源变更，通过冻结检查后交制造发布 |

## 器件、Datasheet 与 BOM

| 技能 | 用途 | 输入与交付终点 | 交给谁或从谁接收 |
| --- | --- | --- | --- |
| [`component-sourcing`](../skills/component-sourcing/SKILL.md) | 查型号、从标准库筛选阻容、核采购字段，按需求导出 AD 表 | 输入精确 C 号、MPN、规格、可选的本地索引或经核对 JSON，按任务交付参数、短名单、批查结果或 HTML/XLSX | 缺项按需要查国内商品页、原厂或渠道。已核验证据供电路设计、BOM 或资格流程使用 |
| [`ee-datasheet-master`](../skills/ee-datasheet-master/SKILL.md) | 从原厂 PDF 取得可追溯的参数和脚位证据 | 入参为精确型号、Datasheet 与问题，输出版本、页码、单位、工况和 min/typ/max | 为电路和固件参数、符号与封装核验、器件资格提供依据。使用可用 PDF 读取路径 |
| [`bom-material-archive`](../skills/bom-material-archive/SKILL.md) | 将 BOM 映射为本地物料档案 | 输入 CSV/XLSX、目标表头和已核对料号，交付保留位号、数量、分组、层级的 CSV 及读回结果 | 采购字段来自 `component-sourcing` 的商品证据。资格判定和制造出包由对应专项处理 |
| [`qualify-pcba-sourcing`](../skills/qualify-pcba-sourcing/SKILL.md) | 按位号核实器件和替代料适用性 | 输入原理图、PCB、BOM、原厂依据和产量，交付逐位号的资格结论和 `sourcing-lock.csv` | 汇合精确身份、封装、脚位、库存和装配证据，把已确定的料件与未决项交给冻结和制造 |

## 机械结构、制造与采购交接

| 技能 | 用途 | 输入与交付终点 | 交给谁或从谁接收 |
| --- | --- | --- | --- |
| [`lab-hardware-cad`](../skills/lab-hardware-cad/SKILL.md) | 用参数化模型设计夹具、支架、适配件和实验硬件 | 输入标准件接口、厂家尺寸和工艺约束，通过可用 CAD 环境交付源码、STEP 及适用的 STL/DXF | 向板级布局提供装配约束。拟制造的机械件按授权交给对应供应商流程 |
| [`release-pcba-fabrication`](../skills/release-pcba-fabrication/SKILL.md) | 汇总一份同版 PCB/PCBA 制造包 | 输入冻结的源、审核结论、BOM、布置和参数，交付 Gerber、钻孔、BOM/CPL、图纸及哈希清单 | 接收器件资格、布局和固件版次。出包后向供应商提交按独立授权办理 |
| [`operate-jlcpcb-order`](../skills/operate-jlcpcb-order/SKILL.md) | 核对嘉立创 PCB/PCBA 报价、装配预览和用户授权的订单动作 | 输入冻结包、采购资格和工艺选项，输出导入/贴装校验、报价或对应订单记录 | 以制造清单为输入。报价、布置、价格和付款环节分别核对现场条件及授权 |
| [`fictiv`](../skills/fictiv/SKILL.md) | 通过已授权供应商会话处理机械件报价、DFM 和订单 | 输入适用 CAD、材料、精度、工艺及数量，运行本地预检并按权限交付 DFM 反馈、报价或订单证据 | 接收机械设计的经过核对的模型与图纸。上传、结算等动作走 [权限门禁](../skills/hardware/references/permission-gates.md) |

## 固件设计、工具链选择与协作

| 技能 | 用途 | 输入与交付终点 | 交给谁或从谁接收 |
| --- | --- | --- | --- |
| [`embedded-firmware-design`](../skills/embedded-firmware-design/SKILL.md) | 实现或修正 MCU 驱动、BSP 与状态机 | 输入板级原理图、芯片、SDK、引脚与时序合同，交付源码和指定构建结果 | 把工件交单次构建或联调，同时把板级接口变更回传电路与 PCB |
| [`embed-ai-tool`](../skills/embed-ai-tool/SKILL.md) | 判断嵌入式工程的实际工具链入口 | 检查项目标志、真实目标、SDK 及环境，交付合适的构建、烧录、调试或采集路径 | 单次任务直接选专项，多步骤用 `workflow` 预览。镜像以摘要和地址布局交接 |
| [`workflow`](../skills/workflow/SKILL.md) | 组织明确请求的构建、烧录、监控和调试步骤 | 输入工程、目标板、镜像、探针或端口，随包脚本只交付离线步骤预览、缺项和只读工件信息 | 实际动作由各构建、烧录、调试或采集技能配相应运行工具执行，每步读回后决定是否继续 |

## 构建

各构建专项使用项目指定的外部工具链，交付构建日志、实际目标、镜像或符号路径。后续写入设备由烧录专项在许可范围内接手。

| 技能 | 用途 | 输入与交付终点 | 交给谁或从谁接收 |
| --- | --- | --- | --- |
| [`build-keil`](../skills/build-keil/SKILL.md) | 用 µVision 构建指定 Keil 目标 | 输入 `.uvprojx`、目标、编译器和 Pack，交付构建日志及实际 AXF/HEX | 镜像进入对应烧录方法，符号可供调试 |
| [`build-iar`](../skills/build-iar/SKILL.md) | 运行 IAR 的指定工程配置 | 输入 `.ewp`、有效配置和 IAR 工具环境，交付日志、链接映射和目标镜像 | 供所用下载器或适配器继续，调试使用相同版本符号 |
| [`build-idf`](../skills/build-idf/SKILL.md) | 用 ESP-IDF 构建实际工程 | 输入 SDK、目标芯片、分区及构建目录，交付应用、引导程序和分区文件，记录烧录地址来源 | 把生成目录及烧录参数交给 `flash-idf` |
| [`build-cmake`](../skills/build-cmake/SKILL.md) | 生成并构建 CMake 指定目标 | 输入源树、构建树、工具链、预设和目标，交付日志及产物路径 | 产物按实际格式交调试或烧录，身份由构建配置和摘要固定 |
| [`build-makefile`](../skills/build-makefile/SKILL.md) | 执行已核实的 Makefile 目标 | 输入项目规则、目标、变量和工具链，交付退出状态、日志与实际工件 | 为设备动作准备证据。递归和钩子行为在调用前检查 |
| [`build-platformio`](../skills/build-platformio/SKILL.md) | 以指定 PlatformIO 环境构建固件 | 输入 `platformio.ini`、环境、板与框架，交付该环境的构建结果和镜像 | 同环境交 `flash-platformio` 或 `debug-platformio` |

## 烧录

| 技能 | 用途 | 输入与交付终点 | 交给谁或从谁接收 |
| --- | --- | --- | --- |
| [`flash-keil`](../skills/flash-keil/SKILL.md) | 通过 Keil 的下载方式写入设备 | 核实目标、镜像、调试器、Flash 算法及复位选项，交付实际日志、写入和校验证据 | 接收匹配的 Keil 构建结果，后续运行另取串口或台架证据 |
| [`flash-idf`](../skills/flash-idf/SKILL.md) | 按 ESP-IDF 生成的地址和清单写入板卡 | 输入芯片、目标板、串口、镜像与地址，按授权交付实际写入和校验记录 | 接收 `build-idf` 的产物以及 flash arguments，之后可交串口监控 |
| [`flash-openocd`](../skills/flash-openocd/SKILL.md) | 用 OpenOCD 写入并核验目标 Flash | 输入探针、板/目标配置、镜像、地址和复位行为，交付写入、验证、停止状态 | 镜像由匹配构建生成。用相同芯片和符号继续 GDB/OpenOCD 调试 |
| [`flash-jlink`](../skills/flash-jlink/SKILL.md) | 用 SEGGER J-Link Commander 写入指定镜像 | 输入探针、精确 Device、接口、速度、文件及适用地址，交付写入和验证证据 | 镜像从构建交接，现场调试可接 `debug-jlink` |
| [`flash-platformio`](../skills/flash-platformio/SKILL.md) | 按确定的 PlatformIO 环境和上传器下载 | 输入上传协议、端口或探针、环境和镜像，分别交付构建、校验、复位和启动记录 | 接收 PlatformIO 工件，实际 uploader 的重建及复位行为按授权核对 |

## 固件与实时故障调试

| 技能 | 用途 | 输入与交付终点 | 交给谁或从谁接收 |
| --- | --- | --- | --- |
| [`debug-gdb-openocd`](../skills/debug-gdb-openocd/SKILL.md) | 用 GDB/OpenOCD 从符号和现场状态定位故障 | 输入匹配 ELF、记录、探针与目标配置，输出回溯、寄存器、故障线索和会话结束状态 | 从构建取符号，现场连接和暂停按授权处理，将证据交固件设计或综合审查 |
| [`debug-jlink`](../skills/debug-jlink/SKILL.md) | 通过 J-Link GDB Server 调试目标 | 输入确认过的板、探针、接口与 ELF，交付指定观测及获准的目标状态变更记录 | 与 J-Link 烧录共用目标识别证据，工件使用对应构建的符号 |
| [`debug-platformio`](../skills/debug-platformio/SKILL.md) | 用项目自带 PlatformIO 调试配置追溯故障 | 输入环境、调试适配器、加载策略和镜像，交付故障寄存器、回溯及代码定位 | 与 PlatformIO 构建和烧录共享环境，现场动作按实际参数核对 |
| [`rtos-debug`](../skills/rtos-debug/SKILL.md) | 分析调度、阻塞、栈、资源和看门狗问题 | 输入同版 ELF、RTOS 配置和按时序对齐的记录，交付可复核的现象和原因证据 | 从调试器、日志或 tracing 获取证据，反馈到固件和综合故障分析 |

## 台架、协议与测量

| 技能 | 用途 | 输入与交付终点 | 交给谁或从谁接收 |
| --- | --- | --- | --- |
| [`serial-monitor`](../skills/serial-monitor/SKILL.md) | 解读串口启动与通信日志，按授权有界采集 | 输入原始日志或已核对端口、波特率、控制线与时限，交付原始字节、时间和解码 | 可在烧录后观察启动，与固件构建版和综合评审对齐 |
| [`serial-shell`](../skills/serial-shell/SKILL.md) | 向已确认设备发送指定串口命令 | 输入端口、Shell 类型、结束符和获准命令，交付原始输入输出及设备结束状态 | 与监控共享端口识别。命令响应和状态作为联调证据 |
| [`can-debug`](../skills/can-debug/SKILL.md) | 分析 CAN/CAN FD 帧并进行获准的监听或发送 | 输入抓包、通道、速率、时间和 DBC，交付帧、周期、错误和未核位域 | 对照硬件接口与固件驱动合同。发送和模式变更单独核对授权 |
| [`modbus-debug`](../skills/modbus-debug/SKILL.md) | 解析 Modbus RTU/TCP 请求和字段映射 | 输入抓包、站号和寄存器手册，交付地址、功能码、异常、端序和缩放证据 | 保存抓包可离线解读。现场读写按实际站点、寄存器和用户许可执行 |
| [`logic-analyzer`](../skills/logic-analyzer/SKILL.md) | 分析数字捕获，按需采集与协议解码 | 输入捕获、通道、电平、采样与触发，交付原始捕获、解码覆盖和时序结果 | 给电路或固件故障分析提供相对时间证据。现场使用已配置的分析仪与软件 |
| [`visa-debug`](../skills/visa-debug/SKILL.md) | 对照仪器手册读取、分析 SCPI 与波形数据 | 输入已有波形，或确认 VISA 后端、资源、通道和允许命令，交付原始记录、仪器身份及采样条件 | 把量程、探头、单位和波形交给电气验收。输出、触发和配置变更按权限处理 |
