# 硬件全生命周期的工程域

按当前问题进入对应专项。需求、接口、安全目标、验证责任和执行证据应能回到同一产品与修订基线。工程经验和原厂应用方法可以确定查证方向，量产或符合性限值须绑定项目适用标准、受控条款和实测对象。[工程知识来源索引](source-index.md)

| 工程域 | 专项参考 | 交给下游的工件 |
| --- | --- | --- |
| 01 系统架构和需求 | [系统安全与需求证据](../../plan-electronic-product/references/system-safety-and-requirements.md) | 工况和故障矩阵、需求到验收的映射、任务剖面、接口及预算、故障反应时序、安全目标和方案选择依据。 |
| 02 器件与供应链 | [器件资格](component-qualification.md)、[选型深度](../../component-sourcing/references/selection-depth.md) | 完整 OPN、封装/端子映射、参数工况、WCCA、合格覆盖、PCN/EOL 与替代发起记录。 |
| 03 电源、功率与 PI/PDN | [电源与模拟审查](../../design-and-review-circuit/references/power-and-analog-review.md)、[工程预算](engineering-budgets.md) | 电源树、状态与上下电依赖、各工况损耗和 SOA、反馈及 PDN 目标、热与关键回路布局要求。 |
| 04 模拟、精密测量与混合信号 | [电源与模拟审查](../../design-and-review-circuit/references/power-and-analog-review.md)、[工程预算](engineering-budgets.md) | 输入和输出可用区、分参考面的误差/噪声预算、采样有效窗口、基准和校准契约、对接测试。 |
| 05 数字总线、高速 SI 与 RF | [SI 验证](si-verification.md)、[仿真与实测](../../hardware-design-review/references/simulation-correlation.md) | 明确协议版次和工作模式，交付电平、阻抗/时序、拓扑、回流、换层、夹具参考面、模型与眼图/BER。 |
| 06 PCB 叠层、Layout 与热 | [板材、装配与环境](../../pcb-layout-review/references/materials-mechanics-and-environment.md)、[热验证](thermal-verification.md) | 板厂工作层叠、材料/铜厚/阻抗公差、热路和实测点、特殊板材和软硬结合动作边界。 |
| 07 EMC、瞬态及绝缘 | [EMC 验证](emc-verification.md)、[绝缘验证](insulation-verification.md) | 端口及回流路径、保护支路残压和应力、状态矩阵、完整隔离边界、产品级试验及报告。 |
| 08 机电与环境可靠性 | [板材、装配与环境](../../pcb-layout-review/references/materials-mechanics-and-environment.md) | ECAD/MCAD 联合基线、装配公差链、板弯/压接支撑、热湿振动任务、涂覆禁区与验证。 |
| 09 仿真建模与实测对齐 | [模型与实测对齐](../../hardware-design-review/references/simulation-correlation.md) | 版本、工具、网表/模型和原始波形，参数和夹具、对齐和独立验证误差、各工况及可用范围。 |
| 10 软硬协同、Bring-up 和阶段验收 | [首次上电与排障](../../hardware-design-review/references/bring-up-troubleshooting.md)、[阶段门禁](../../manage-pcba-program/references/stage-gates.md) | 探测与安全停止条件、按电源和启动依赖保存实测，关联硅版本、固件配置、EVT/DVT/PVT 各自判据。 |
| 11 DFM/DFA/DFT 与制造放行 | [DFM/DFT 验证](dfm-dft-verification.md)、[制造放行清单](../../release-pcba-fabrication/references/release-checklist.md) | 工厂能力窗口、单一同版导出和 CAM 回读、故障模型覆盖与盲区、FAI/试产记录、签核和变更回流。 |

每个专项先读该域输入与量测假设，随后带着完整型号、标准版次或已冻结工件去查 [来源索引](source-index.md)。输出标明计算、仿真、台架、实物验收或原厂资格，并对缺工况、缺正文、未证可达角落和测量不确定度跨限的项目给出待验证原因。依赖项补齐后核对受影响的相邻域。

## 跨域评审如何串起来

以带模拟采样和外部 RS-485 的板为例。先由需求专项冻结精度、工作范围、响应和故障允许状态，再向器件专项交完整 MPN、封装、保证参数和原厂定位。用电源与 AFE 的最坏工况确定电感峰流、PDN 动态预算、采样阶跃、参考电流和首个有效码。接口专项增加最快边沿、线束、端接及共模，PCB 把这些约束落在实际回流、层叠、热路径、机械包络与隔离边界上。独立运行按工况指定的规则、仿真和读回，每项保留真实覆盖。冻结时结合同版 CAM、工艺、BOM/CPL 和明确的测试故障分母。若实测是发帧后码偏移或复位，按 [首次上电与排障](../../hardware-design-review/references/bring-up-troubleshooting.md) 取同步证据，再回到供电、参考、采样或回流等源头修订。

正式评审期间，用 [证据交接](evidence-and-backends.md) 核对上游工件摘要和实际执行范围。版次、变体或工况改变时，标出受影响结论、确认可复用部分并重跑相应检查。轻量问答只进入有关的专题及验算。

## 现场工具与生态资料的使用

- 先用所选 EDA 版本支持的原生只读报告、导出物或已回读文件取证。KiCad IPC 的无界面能力随版本而异，别用新版本文档推断旧版。Capture 的内存读回不一定代表关闭再打开后的持久化状态。 [KiCad IPC 版本限制](https://dev-docs.kicad.org/en/apis-and-binding/ipc-api/for-addon-developers/index.html) · [Capture SPB17 维护者的版本化记录](https://github.com/daveyJ-sgs/Cadence-MCP-SPB17/blob/cc7d85b4935264099483e76decd89767a72dd9af/docs/capture_api_notes.md#L112)
- 接入外部 MCP 时，以固定版本核实许可证、工具能力、本地/网络边界、写入副作用和失败后状态。用同一个冻结工件和同一项验收，对照原生输出复核缺项。KiCad MCP Pro 的固定提交许可为 AGPL，旧索引中 MIT 的记录不能沿用。 [KiCad MCP Pro 的固定版本许可证](https://github.com/oaslananka/kicad-mcp-pro/blob/80078bda6326d0de2f6d165b7ad6b773d028e3b2/LICENSE)
- 结构化评审可借鉴组件、引脚、网络及证据定位。多轮判读共享输入时仍须借助独立工程事实。波形导出也要确认采集停止、窗口和格式副作用，并记录恢复状态。未完成的工件保留失败状态。 [DRCY 实现说明](https://arxiv.org/html/2603.15672v1) · [Rigol MCP 的完整读取边界](https://github.com/erebusnz/rigol-mcp#full-acquisition-memory-export)
