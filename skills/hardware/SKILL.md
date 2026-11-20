---
name: hardware
description: "负责硬件规划、设计、深度审查、ECO 或替料、仿真验收、Bring-up 排障和制造放行。主动查本机知识和最坏工况，作工程取舍，调度专项并验收。查料、单点计算、绘图和报告读取可直接进入专项。"
---

# 硬件设计

$hardware 持有需求、工程判断、跨域影响及交付验收。专项实施或取证，项目状态保存批准和版本，后端只承担实际操作。可独立使用，也可接在全局 `routing-skills` 之后。

## 主动工程流程

按交付目标选择 `plan/design/review/eco/verify/bringup/release`。已点名的专项用于实施，工程判断仍走本流程。日常设计、局部审查和排障使用轻量启动。精确查料、单点计算、既定接线绘图、转换和已有报告提取直达工具。仅正式评审、跨阶段交接、正式 ECO 和制造放行保存工程 case 并运行完整 `assess`。

1. **确定交付范围和工况**。锁定允许来源、当前版次与拟交付物。筛正常极限、状态转移、环境/寄生、故障与生产/测量。独立设计用给定规格和允许的知识，仅在授权且必要时查旧工程。
2. **先展开原型风险，再查原文**。调用 [design_flow.py](scripts/design_flow.py) `start <mode> --intent "任务目标"`，补 `--prototype` 确认关键功能块。根据输出的 `knowledge_route` 选读基础理论、设计参考和实测案例。用 `basis --rule` 或 `basis --theme` 查适用原页，缺原件时先查对应 11 域参考并定向补证。项目标准与器件限值独立核对。 [工程知识地图](references/knowledge-map.md)
3. **做取舍与反证**。先核安全、绝对额定值、不可逆故障和制造硬冲突。主动提出会推翻结论的最坏状态和区分验证。边界跨限、动态或寄生能左右决策时按 [模型升级](references/design-workflow.md#模型升级与反证) 补证。非关键缺项带有界假设继续做出可推进工件。权衡减料、通用封装与二供、测试点、可断开通路及有用的滤波/吸收预留。
4. **执行和回流**。给专项工件身份、工况、目标产物、判据与许可。用已有脚本验证，读回不同证据层。ECO 用 `impact` 标出失效结论；排障保留竞争假设、伪影和最小区分实验；制造区分冻结、预检与实体放行。正式交付运行 `assess`，项目签核和 L0–L3 授权另核。

具体命令、实用设计判据、正式工件和验证见 [工程决策与交接](references/design-workflow.md)。已有有效证据按版次和工况复用。

`required_checks` 中有 `phase_action` 时，将该行动落实成当前阶段的决定、测量判据或缺证。读到的原文用于确定适用条件；闭环按实际工况及工件核。正式交接保留适用检查 ID 和证据，后续阶段据此复用或重验。

## 专项调用与操作权限

1. 确定动作、源工件或设备、平台与版本、已保存或现场状态、所需证据、已授权范围和停止点。关注实际意图。原理问答、工具介绍、引用旧提示词等按所请求的资料任务处理。
2. 同名专项优先采用用户精确点名的来源，其次沿用项目或当前流程已选来源，其余采用当前有效的随包来源。固定批处理调用随包脚本。用户或项目已选其他来源时，按该来源自己的入口执行。遇到入口冲突、平台差异或跨阶段交接时读 [路由矩阵](references/route-matrix.md)。核对必要的可用性与实际签名，同一阶段就同一职责只选一个入口。
3. 在现场接入、写入、构建、控制设备和外发前，用 [权限门禁](references/permission-gates.md) 按实际动作及参数定级。L0 离线只读，L1 现场或在线只读，L2 隔离副本写入与有界本地动作，L3 原工程写入、模态 DRC、Computer Use、硬件控制及外发。若只授权了较低风险动作，先交付可独立完成的工作，再请求本次升级许可。
4. 按当前约定让专项执行并读回结果。跨阶段交接沿用证据和工程版次。发现源头问题时暂停受影响的下游操作，标记依赖结论失效并回流重审。实际通过、仍缺的证据和待许可动作分别记录。

按交付深度从能完成请求的最短入口开始。单项事实用定向工具，已有工件的重复处理用脚本，工程决策或冻结才进入相应核验。已有证据足够就交付，缺一项补一项。采购、建库、报价和出文件按当前目标分别触发。

画图时按产物选入口。说明或教程用的电路图走 [Schemdraw](../draw-schemdraw-circuit/SKILL.md)，未指定图片格式时用 SVG。要求可在 EDA 中编辑的原理图时走 [电路设计](../design-and-review-circuit/SKILL.md) 与目标平台。要求运行和波形时选经过核对的仿真入口。

## 工程资料检索

需要用手边的数据手册、应用笔记、标准或教材支持结论时，按 [工程资料检索](references/engineering-knowledge.md) 定位版本、查正文并回读原页。已有逐页 OCR 数据时，直接用 [本地 OCR 检索](references/ocr-books.md)。引用时保留版次、物理页和已确认的印刷页。通过外部服务检索私有资料时，按[权限门禁](references/permission-gates.md)先核对发送范围。

设计或审查需要确定核验依据时，先按 [设计与审查规则](references/design-review-basis.md) 查与当前工况相关的规则，并把适用条件、来源及闭环证据交给对应专项。

当任务需要定量核对 SAR ADC 建立误差或 PDN 目标阻抗时，使用 [工程预算](references/engineering-budgets.md) 的离线计算。将模型结果和实际工程证据分别交给下游。

涉及 SI、EMC、热与降额、绝缘、DFM／DFT 或器件资格时，按 [工程核验与交接](references/engineering-verification.md) 选读对应主题。已有明确输入时用同页的离线命令，工程结论随适用条件、项目限值和证据交接。

## 工作深度与结果交接

正式记录字段、后端状态与调用示例见[证据外壳与后端诊断](references/evidence-and-backends.md)。

单点问答、单项查料及模型计算直接给条件、结果、适用范围和缺项。专项审查、仿真验收、制造冻结或阶段门禁使用版本化 `evidence_envelope`。在三个已接入的批处理 `kicad-report-check`、`release-check`、`bench-check` 上加 `--formal`。原始工件与专项状态随记录保留。KiCad 的 `no_reported_findings` 只描述该报告的可见项目。保守包络触碰界限时，查能否实际达到或由独立证据证明越界。

按 [11 域工程索引](references/lifecycle-domain-index.md) 选取本次主题，按 [来源版次与页码](references/source-index.md) 核查采用的原文。确定性计算见 [计算输入和退出码](references/model-checks.md)。运行条件缺失时，用 [backend_doctor.py](scripts/backend_doctor.py) 离线核配置、安装与已有观察证据。

保存态解析先选一个解析器和一个目标文件。现场经授权后，先读目标工程、文档身份与活动窗口，限用对应对象族。空列表、焦点不符、缺编译或不支持时记录覆盖缺项。Multisim 先选既有网表/结果或经批准的副本，核模型与测点后才选择所需分析。写后超时记 `outcome_unknown`，先独立读回目标和差异。可信批准来自用户或宿主授权记录，模型填写的 `approved=true` 无效。

## 可直接运行的批处理

任务已明确匹配下表、采用本机入口且输入与权限已明确时，直接调用 [hardware_tool.py](scripts/hardware_tool.py)。用 `list --json` 取固定目录，`<命令> --help` 取参数，必要时以 `--plan <命令> …` 预览本次读写。流程步骤、缺项和停止结果由专项脚本返回。

| 任务 | 子命令 |
| --- | --- |
| 盘点保存的 AD 工程成员、多个图纸、板卡或定位位号 | `ad-saved` |
| 汇总已有 KiCad ERC/DRC JSON 的严重度、排除项和覆盖 | `kicad-report-check` |
| 从保存的 KiCad 文件生成新的 ERC/DRC 证据 | `kicad-native-check` |
| 按已核对的网表和量测合同执行后台仿真 | `spice-run` |
| 物料档案预检、批量映射或按已核对证据补 C 号并出 CSV | `bom-archive` |
| 将现成的选型 JSON 转为底稿、HTML 或按需 Excel | `selection-export` |
| 核对同一装配变体的 BOM、CPL 和不贴装位号 | `assembly-check` |
| 核对采购资格表或冻结制造包 | `sourcing-lock-check` / `release-check` |
| 按给定限值核对既有台架测量 CSV | `bench-check` |

固定批处理只包含离线读取和已指定工件的本地输出。固件、仿真和其他已有入口见 [批处理用法](references/local-tools.md)。现场、前台、设备操作与外发继续按权限门禁处理。

## 器件任务的交付停点

- 找器件、核对已知型号或筛选阻容规格时，优先复用可用证据。用户提供标准阻容索引时走 [本地查询与回退](../component-sourcing/references/sourcing-queries.md#标准库优先与外部检索)。补证、现货和数量价用当前实际可用的定向渠道工具，默认在正文交付。只做物料档案转换或补齐渠道料号时，由 `bom-material-archive` 交付所需 CSV。原理图、网表、PCB 和器件库按实际需要进入。
- 已有一份精确 C 号或完整 MPN 清单需要查技术详情时，直接运行器件专项的 [批量精确查询](../component-sourcing/references/batch-lookup.md)，沿用仍适用的报告只补缺项。多位号按同一组硬条件选型时，先用 [选型条件分组](../component-sourcing/references/selection-depth.md#批量同条件分组)。
- 用户要求为工程选用或替换器件时，即使只有一个位号，也由 `component-sourcing` 整理已核验的选型数据并按 [导出流程](../component-sourcing/references/ad-selection-export.md) 生成默认的 HTML。用户明确指定的文件格式和范围优先，Excel 按需从同一份数据导出。工程字段及商品页证据以 [AD 字段规则](../component-sourcing/references/ad-field-rules.md) 为准。

## Altium 与日常查询

- 审查或读取 Altium 保存文件时，先用离线库或保存工程解析。离线缺少必要证据，自动转现场前须单独请示。已获桥接许可且现场仍无法解决时，再单独请示 Computer Use。桥接读取不扩大到模态 DRC、写入或桌面操作。
- 用户明确要求“查看当前已打开的 AD 工程/板卡”时，已授权该现场的 L1 只读桥接。日常选型或查料请求直接覆盖 `components` 的 L1 只读查价。在这两类只读任务中，新增 L2 写入或 L3 动作须另外确认。
- 离线库遇到 `allowed_paths` 拒绝时，先问用户指定允许的目录或副本路径。保留原工程和现有权限边界。
- `ltspice-mcp` 优先后台网表仿真。SOLIDWORKS 优先用本机 SDK 和模型，`swapi-pilot` 只用于公开 API 标识查询。3D 文件、几何数据及工程资料默认在本机处理，外发须事先获批。若需运行本地 COM 脚本，先检查实际代码及参数。任何可能抢焦点、弹交互对话框或发送键鼠输入的动作，都要按 [前台和外发许可](references/permission-gates.md#spice-与-solidworks-前台和外发许可) 在执行前取得用户针对本次动作的批准。

本技能的门禁通过代理在调用前检查、申请及等待来执行。具体接口的技术限制和审批契约仍按实际工具处理。复核技能行为时使用 [验收用例](references/acceptance-cases.md)，把模拟轨迹与现场执行证据分开。
