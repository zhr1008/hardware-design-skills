# 热设计与器件降额

先判定稳态、重复脉冲或单次故障。把外壳、风量、环境、铜铺面、器件损耗和实际热路径放在同一工况。对照项目结温、额定工作条件和寿命目标，再选计算或实测。

## 模型与适用条件

| 任务 | 定量模型与验证 |
| --- | --- |
| 稳态有封装顶面温度 | 适用 `Ψ_JT` 时，`T_J ≈ T_top + Ψ_JT · P_diss`，温度用 °C，`Ψ_JT` 用 °C/W，功率用 W。顶面中心布置低扰动探头，核对风量、散热路径、封装和板形；用匹配热模型或验证覆盖这类差异。具有顶面散热片、特殊灌封、异质多芯片时，不能直接套用原试验配置。 [TI SPRA953D，2024，§3 式 8、表 3-1](https://www.ti.com/lit/an/spra953d/spra953d.pdf) |
| 名义 `θ_JA` 与热路径 | 数据表 `θ_JA` 用规定试验板和环境表征。实际板的铜面积、层数、热焊盘、风量和邻近发热可能改变温升。掌握相同路径下的有效热阻时可估算 `T_A+P_diss·θ_JA`；底部或顶面 `θ_JC` 对应该规定热流边界，先识别测点/散热条件。 [TI SPRA953D §1–3](https://www.ti.com/lit/an/spra953d/spra953d.pdf) |
| MOSFET 脉冲与 SOA | 方波单脉冲、已知壳温和适用瞬态热模型时，可估 `ΔT_J=P·Z_θJC(t)`。再按实际 `V_DS/I_D/t`、重复率及起始壳温核 SOA。线性区的局部热不稳定受器件限制，在原厂不允许的范围内禁止用恒功率反推安全边界。重复脉冲按厂家瞬态曲线、占空比或可靠热模型重算初始温度，不沿用冷启动单脉冲结论。 [ADI MOSFET SOA 与热插拔，Transient Thermal Impedance、Spirito 区](https://www.analog.com/en/resources/technical-articles/mosfet-safe-operating-area-and-hot-swap-circuits.html) |

## 原厂失效对照与算例

TI SCAA145 的 Application 2 在 25 °C 环境、计算功耗 0.202 W 下，用同种 RKS 封装对照热焊盘悬空和经热过孔连地。记录的壳温分别为 57.2 和 32.5 °C。以资料给出的 10.3 °C/W 计算，结温估值约 59.28 和 34.58 °C。把数据表的 67.7 °C/W 直接当本板热阻，则两者都会算成约 38.68 °C，掩盖真实的散热路径差异。原文直接测了壳温，结温由模型估得。 [TI SCAA145，Application 2，表 2](https://www.ti.com/document-viewer/lit/html/SCAA145/GUID-771D0EEB-6C3C-46D3-9AE4-A886F0AFF154)

ADI 的热插拔设计例把同一 1 ms、40 V 的 SOA 点从 25 °C 壳温下约 20 A，降到 62 °C 下约 14 A。按文中系数 `20/1.42 ≈ 14.08 A`。只有原厂允许在该机理和曲线段应用类似温度缩放时才可迁移该做法。 [ADI Understanding Hot Swap，式 12–15、图 6](https://www.analog.com/en/resources/analog-dialogue/articles/understanding-hot-swap.html)

## 量化验收

上游 `thermal` 的 T1 按装机路径和测温不确定度计算结温区间。T2 对电解、固态或混合电容使用精确系列的纹波与寿命条件，并用寿命终点的 C/ESR 核系统功能。MLCC 的偏压和温漂走 `effective-capacitance`。功率开关级或重复保护触发 T3 时，记录初温和周期，按实体热端口接入散热边界，分别验结温及器件 SOA。

项目应明确结温上界、降额依据、有效工况与不确定度。示例给封装顶面 104～108 °C、适用 `Ψ_JT` 1.1～1.5 °C/W、耗散 2.0～2.4 W，保守区间为 106.2～111.6 °C。与项目上限 110 °C 相交，待补测或降温。若采用的数据只给典型 `Ψ_JT` 且无法界定模型差异，不能把典型值作上界。开关损耗、电阻随温度的变化及热平衡按实际热路径闭环。

```powershell
python -X utf8 scripts/engineering_validation.py junction --top-c 104 108 --psi-c-per-w 1.1 1.5 --power-w 2.0 2.4 --limit-c 110
```

交台架时保留最坏输入电压、负载、占空比、器件和板版次、外壳安装、环境温度/气流、仪器校准、测点照片和达到稳态的判据。对起动、堵转、短路和重试工况分别报告削峰、保护响应时间、SOA 裕量及恢复。热与资格证据分别记录环境工作范围、工作结温和应力试验温度。
