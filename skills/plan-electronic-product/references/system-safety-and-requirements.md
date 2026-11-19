# 系统需求、接口与安全度量

把业务目标落实为带 ID 的需求，每项包含运行状态、量值和单位、适用环境、允许误差、失效后果、验证方式及证据责任人。用接口控制文件交付电压/时序、正常与单故障下的能量、连接器和机械边界、复位/断电默认态、互锁及外部依赖。把供能、误差、温升、时延和容差预算分配到可以单独验证的子模块，再用系统测试关闭整机要求。ISO/IEC/IEEE 15288 的公开范围支持生命周期过程选择。 [15288:2023 官方目录](https://www.iso.org/standard/81702.html)

安全相关产品先确认产品标准、法规、客户要求和经批准的安全目标，按这些输入确定危险分析、任务剖面、独立性与失效反应。把故障检测、传播、隔离和执行环节的最坏延时相加，核对 FTTI 或过程安全时间及最终状态，覆盖断电、卡死、共因和通信丢失。单项器件有安全资料时，取安全手册里的诊断、假设和外部依赖，再落实到当前板。

## 故障分类与判定

| 度量 | 输入和边界 |
| --- | --- |
| SPFM | 对该安全目标相关的失效率 `λ_SR`，按互斥分类统计单点 `λ_SPF`、残余 `λ_RF` 等。`SPFM=1−Σ(λ_SPF+λ_RF)/Σλ_SR`。 |
| LFM | 取潜伏多点贡献 `λ_MPF,L`，`LFM=1−Σλ_MPF,L/Σ(λ_SR−λ_SPF−λ_RF)`。分母包含范围内相应安全故障和多点故障。 |
| PMHF | 核具体安全目标的单点、残余、相关多点组合、诊断间隔、任务时间和依赖失效。采用批准的 PMHF 或条款允许的 EEC 分析路径。 |
| IEC 61508 安全完整性 | 低需求模式评估 PFDavg，高需求或连续模式使用 PFH。按需求模式与受控标准取目标。 |

各失效率统一单位。范围不明、分类相互重叠、合计不合、分母为零、诊断覆盖及联合故障模型缺证据时保留待验证。SPFM/LFM 只是对应指标的核算，PMHF 不使用无分类的器件 FIT 相加。FIT 与 ppm、MTBF 与任务寿命、SIL 与 ASIL 各有适用定义。

来源边界应随项目记录。ISO 26262-5:2018 本轮只有官方目录和范围。Infineon 原厂复述的 B/C/D 三档 SPFM 目标为 90%/97%/99%，LFM 为 60%/80%/90%。PMHF 的 B/C 档 100 FIT 与 D 档 10 FIT，Infineon 使用 `<`，TI SFFSAY3 表 1-2 使用 `≤`。恰好等于边界时保留待判，用获授权标准与项目安全计划裁决。没有安全分析或经批准的实际条款时，可提交需求、模型、风险和缺项。 [ISO 26262-5](https://www.iso.org/standard/68387.html) · [Infineon 故障分类](https://community.infineon.com/t5/Knowledge-Base-Articles/AURIX-MCU-ISO-26262-fault-classification-of-a-HW-element-and-associated-HW/ta-p/379692) · [Infineon FMEDA](https://community.infineon.com/t5/Knowledge-Base-Articles/Failure-Modes-Effects-and-Diagnostic-Analysis-FMEDA-AURIX-MCU/ta-p/372906) · [TI SFFSAY3 表 1-2](https://www.ti.com/lit/pdf/sffsay3) · [IEC 61508](https://webstore.iec.ch/en/publication/5515)
