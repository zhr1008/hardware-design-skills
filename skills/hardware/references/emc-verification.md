# EMC 验证

## 确定适用要求和受试状态

线缆屏蔽搭接或回流异常进入 `emc-shield-current-path`，将不同注入位置分别画成闭合路径。改搭接后至少重查受影响的相邻端口、复位/供电和隔离边界。工程交接保留原始基线、对照原始记录、实际覆盖范围和适用的产品判据。 [规则、原图与定位](knowledge-map.md#emc)

从销售地区、产品类别、安装环境、外部端口和合同要求确定适用标准。对每条要求记录标准版次及条款、受试设备（EUT）硬件和固件版次、供电和负载、机壳与接地状态、线束与外设、运行模式、检验方法、等级或限值、允许的性能退化及判定规则。标准、合同或项目规定指定多个工况时，逐项取证。

| 证据 | 对应对象和关键信息 | 原始依据 |
| --- | --- | --- |
| HBM、CDM 等器件 ESD 数据 | 分别按人体模型和带电器件模型评价器件敏感度。保留标准、额定值、引脚组合和资格报告标识，用于器件处理与制造风险判断。 | [ESDA/JEDEC JS-001-2024](https://www.esda.org/store/standards/product/392/ansiesdajedec-js-001-2024/)、[JS-002-2025](https://www.esda.org/store/standards/product/451/ansiesdajedec-js-002-2025/) |
| IEC 61000-4-2 整机 ESD 抗扰度 | 评价约定配置和运行状态下的系统功能、恢复和损伤。采用产品规范确定适用等级与性能要求。IEC 2025 年第 3 版增加了空气放电枪头校准要求，附录 E 涉及接触放电选点和脉冲次数，附录 I 给出特定设备布置，附录 K 承接旧版第 9 章的内容。项目按所引用的版次执行。 | [IEC 61000-4-2:2025 Ed. 3.0，范围和版本变更](https://webstore.iec.ch/en/publication/68954) |
| 传导或辐射发射 | 限值按端口、频段、设备分类和市场确定，再锁定测距、检波器和带宽。近场探头、线缆电流探头和屏蔽对比用于定位耦合路径。合规判定使用适用测试布置的读数和报告。 | [47 CFR §15.109，辐射发射示例](https://www.ecfr.gov/current/title-47/chapter-I/subchapter-A/part-15/subpart-B/section-15.109)、[§15.35，检波器与带宽](https://www.ecfr.gov/current/title-47/chapter-I/subchapter-A/part-15/subpart-A/section-15.35) |

## ESD 设计校核

1. 沿外部放电点、信号或屏蔽、TVS、回流端、受保护引脚标注电流路径和参考节点。检查 TVS 是否靠近入口，主走线是否直接到达保护焊盘，接回流端的走线、过孔或壳体搭接是否形成高电感，未保护线路是否与放电路径长距离并行。若要调整屏蔽接地或跨隔离域的连接，同步按绝缘要求核对。 [TI SLVA680A，2022-04，§2.1–2.4](https://www.ti.com/lit/an/slva680a/slva680a.pdf)
2. 用正常信号最大摆幅、偏置、温度、电源误差、正常共模和适用故障工况核对器件工作电压、极性、漏电与寄生电容。根据相关脉冲的钳位曲线核对下游瞬态耐受，并记录所用脉宽、极性、峰值或通流区间及温度。分别处理 ESD、EFT 和浪涌的波形和器件数据，尤其核对额定脉冲形状和测试条件。 [TI SSZB130E，2025-08，§2](https://www.ti.com/lit/sg/sszb130e/sszb130e.pdf?ts=1794525201806)
3. 用相同极性和脉宽的两个已通流测点估算动态电阻 `r_D = (V₂ − V₁)/(I₂ − I₁)`，以 `V₀ = V₁ − r_D × I₁` 得到局部拟合截距。正极性脉冲的残压可简化估算为 `V_node(t) ≈ V₀ + r_D × I_TVS(t) + L_eff × dI_TVS(t)/dt`。`I_TVS` 取流经 TVS 的支路电流，`L_eff` 取夹具采样点之外、实际相关支路的等效串联电感，电流和斜率对应同一时刻。若本地参考地移动或下游分流显著，补建对应路径或直接测量引脚对本地参考的残压。分别核对上升沿尖峰和后续通流区间。 [TI SLVA680A，2022-04，§2.1、§2.4](https://www.ti.com/lit/an/slva680a/slva680a.pdf)、[TI SSZB130E，2025-08，§2.6](https://www.ti.com/lit/sg/sszb130e/sszb130e.pdf?ts=1794525201806)

**公开试验数据。** TI 在数据线保护器件对比中公布了标注为 25 kV IEC ESD 冲击的两条波形。图 7 及正文给出的约 5 ns 峰值分别为压敏电阻约 1,500 V、TVS 约 400 V。证据覆盖该对比的器件端波形。对具体 EUT，应独立验证实际引脚残压和系统功能。 [TI SLVAFR3，2024-02，图 7 与 Clamping Voltage 小节](https://www.ti.com/document-viewer/lit/html/SLVAFR3/GUID-7F89B48F-6B8F-45D0-A2F4-22806A8048AB)

**可复算的失效示例。** 假设同脉宽正极性 TLP 取点为 `(8 A, 11 V)` 和 `(16 A, 15 V)`，得到 `r_D = 0.5 Ω`、`V₀ = 7 V`。对一个假设的脉冲时刻取 `I_TVS = 12 A`、`dI_TVS/dt = 3 A/ns`、`L_eff = 1 nH`，模型估算 `7 + 0.5 × 12 + 1 × 3 = 16 V`。若虚拟项目 `DEMO-EMC-001 Rev A` 的同极性、同瞬态窗口和本地参考节点上限为 `15 V`，估算超限 `1 V`。缩短支路使 `L_eff = 0.4 nH` 时估算 `14.2 V`，名义余量 `0.8 V`。测量并核对时域与工况，再确认是否有足够余量。模型参数、上限和失效均为教学设定。TLP 对特定 IEC ESD 条件的经验映射仅用于比较，实际支路波形取自适用的模型或测量。 [TI SSZB130E，2025-08，§2.6](https://www.ti.com/lit/sg/sszb130e/sszb130e.pdf?ts=1794525201806)

## 预兼容测量和验收

- **ESD 功能验收**。覆盖测试矩阵中的直接接触、空气及间接放电中适用的方式，记录点位照片、极性、电压、次数、间隔、布置、校准记录和 EUT 状态。持续监控关键功能并在试验后复验。对复位、通信错误、输出异常、数据保持、恢复方式和恢复时间逐项与产品性能要求比对。在可比批次和同一试验配置下对照修订前后的问题点，再补跑受改动影响的工况。
- **ESD 残压诊断**。记录测量节点和参考、极性、观测窗口、夹具与接地、探头带宽和去嵌方式、重复结果和不确定度。合格条件引用与波形、窗口和极性匹配的项目允许峰值或耐受曲线。以同一虚拟项目的 `15 V` 上限为例，模拟测量 `14.2 ± 1.0 V` 的区间 `[13.2, 15.2] V` 跨越上限，结果为不确定。缩小测量不确定度或增加设计余量后复测。
- **发射验收**。保留最大发射的频率、测距、天线高度和极化、检波器和带宽、EUT 配置、修正后的读数、不确定度和报告定位。对适用的美国 Class B 数字设备示例，假设按 `47 CFR §15.109(a)` 在 `3 m` 检验 `80 MHz`，该处限值 `100 µV/m`，以 `20 × log₁₀(100)` 换算为 `40 dBµV/m`，按 `§15.35(a)` 采用 CISPR 准峰值及对应带宽。若虚拟修正读数 `38.2 ± 1.4 dBµV/m`，上端 `39.6 dBµV/m`，按下述项目判定规则该频点余量为 `0.4 dB`。最终结论覆盖计划中适用的频段与模式。 [eCFR 47 CFR §15.109(a)、(c)](https://www.ecfr.gov/current/title-47/chapter-I/subchapter-A/part-15/subpart-B/section-15.109)、[§15.35(a)](https://www.ecfr.gov/current/title-47/chapter-I/subchapter-A/part-15/subpart-A/section-15.35)

当项目采用完整区间判定时，对包含等号的上限 `L`，`x + U ≤ L` 为通过，`x − U > L` 为不通过，其余为不确定。保留 `U` 的来源、覆盖说明和单位。合同、标准或实验室已规定判定规则时采用该规则。本地 `engineering_validation.py` 的 `limit` 子命令只复算输入的单项边界，正式符合性按适用要求和试验报告确认。

```powershell
python -X utf8 scripts/engineering_validation.py limit --direction max --value 14.2 --uncertainty 1.0 --limit 15 --unit V
python -X utf8 scripts/engineering_validation.py limit --direction max --value 38.2 --uncertainty 1.4 --limit 40 --unit 'dBuV/m'
```
