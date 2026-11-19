# 首次上电、测量伪影和故障排查

准备工件时绑定样品号、板/BOM/壳体版本、硅修订、固件提交/选项和配置、负载线束、环境、仪器与校准。高能回路和测试动作按项目受控台架流程执行。开始前按电源轨和实际器件记录限流、过压、温度以及异常停止线，确认操作范围内的放电与隔离条件。

| 检查阶段 | 出现异常时优先区分 |
| --- | --- |
| 断电检查 | 确认极性、方向和焊接，比较同版良板的阻抗与充电曲线。低压大电流核心轨的正常低阻、容性浪涌、误焊和真实短路分开查。保留基线读数和接线。 |
| 最小供电 | 从辅助轨到局部轨同步采 VIN、轨、EN、PG、时钟与 reset。按实际偏压 C、爬升率与负载预算浪涌 `I≈C_eff·dV/dt+I_load`。触限后停机，区分供电下陷、正常浪涌、稳态短路、UVLO 周期重启、意外反灌与方向问题。 |
| 最小固件 | 核 Boot/strap 采样、引脚电平域与 AF、复位窗口、时钟默认态、调试器、ROM/片内启动。JTAG 可访问而 DRAM 失败时分轨、时钟、训练和 byte lane。串口无输出检查 pinmux、电平、时钟和实际启动路径。 |
| 逐区复现 | 一次改变一个变量并记录可重复条件。对照良板、同固件、已知负载、线缆和温度。复位、放宽超时和临时飞线保留为定位证据，修订回到原理图、PCB、固件、器件或工艺源头后复测。 |

按精确器件获取数据手册、参考手册与硅修订对应的勘误。STM32F4 的 AN4488 Rev 7 是板级电源、复位、Boot 和调试入口。已有核对记录发现 ST 目录将 ES0182 标作 V19，实际 PDF 封面为 Rev 18，仍须获取当前硅版匹配的受控勘误。固件未使能外部晶振时，将软件配置与硬件不起振分开排查。 [ST AN4488 Rev 7](https://www.st.com/resource/en/application_note/dm00115714.pdf) · [ST 目录](https://www.st.com/en/microcontrollers-microprocessors/stm32f4-series/documentation.html) · [ES0182](https://www.st.com/resource/en/errata_sheet/es0182-stm32f405407xx-and-stm32f415417xx-device-errata-stmicroelectronics.pdf) · [TI 启动验证](https://www.ti.com/lit/ug/sprad21j/sprad21j.pdf) · [U-Boot 初始化](https://docs.u-boot.org/en/v2025.01/develop/init.html)

## 排除测量伪影

- 长探头地线引入回路电感与天线耦合，可能产生 `L·di/dt` 或和探头输入电容谐振。先核安全接地和额定值，再用适当的短接地弹簧、同轴/差分连接，在同带宽下复测。核对补偿、触发、混叠、探头输入电容、测试点负载和参考位置。
- 探头和示波器的组合带宽按最快关注边沿选择。 `t_r,测²≈t_r,DUT²+t_r,scope²+t_r,probe²` 只在相容的近似响应中使用。差分探头须核共模/差模范围、频率降额和 CMRR，保留高共模下泄漏误差。保护地维持连接。
- 同步原始 CSV/波形和接线照片、探头设置、采样/滤波、校准、原始触发条件、量值不确定度与项目决策规则。测量区间跨限时保留待验证。VNA 另记录参考面和夹具去嵌，眼图记录 UI、采样和均衡。 [Tektronix 探头手册](https://download.tek.com/document/02_ABCs-of-Probes-Primer.pdf) · [NI Guard Band](https://www.ni.com/en/shop/services/hardware/calibration-services/calibration-services-guard-band-implementation.html)

例如传感板在 RS-485 发帧时首个 ADC 码偏移、偶尔 reset，同时测 ADC 输入/REF、供电、DE 与 reset。保持时间关系，分别对照等效负载阶跃、不发帧、固定通道和跨通道、线缆或机壳配置及实物 BOM。电源、参考回路、采样时序、接口回流、装配各有相互可区分的实验。记录最小可复现状态、支持与反驳证据、修订和必要复测。 [采样及电源的审查入口](../../design-and-review-circuit/references/power-and-analog-review.md)

## 阶段采证

- EVT 首先覆盖冷/热慢启、快速断续电、电源先后、复位/Boot/调试、固件配置和最小系统。保留同版原始时间序列。
- DVT 覆盖项目任务剖面的输入/负载/温度角落、环境、异常恢复与抗扰，记录受控方法、严酷度、夹具和失效判据。统计零失效上界需明确样本、时长及独立性。 [NIST 比例置信界](https://itl.nist.gov/div898/handbook/prc/section2/prc241.htm)
- PVT 保存工序、测试覆盖盲区和复测、工装/程序、首过和返修、生产批次与替代料追溯。改版后的关闭证据进入 [阶段门禁](../../manage-pcba-program/references/stage-gates.md) 与 [实测验收](bench-results.md)。
