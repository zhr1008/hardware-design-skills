# 电源、模拟前端与保护的审查交接

## 电源、PI 和保护

1. 画出电源轨、正常/启动/掉电/热插拔、反灌、UVLO、限流及短路后恢复状态。给每条电流实际返回路径、峰值/均值/RMS、温度及负载范围。检查热环路、反馈取样、Kelvin 源极连接和隔离屏障。
2. 先判断拓扑和 CCM/DCM、控制方法及工作点，再计算纹波、RHPZ、损耗、环路、磁饱和与热。最大占空比、最低/最高 VIN、负载和温度跨模式时分开建模。瞬态用实际 `VDS(t)·ID(t)`、脉宽、初始结温、重复重试和冷却条件核线性 SOA。
3. 把电源限差分给稳态偏差、负载阶跃及纹波。用偏压、温度、容差、老化后的 C 和安装 ESR/ESL 检查 PDN，评估峰值与跨端口传输，再用负载阶跃、压降和阻抗试验核真实板。环路注入位置、幅度、动态负载及相位需复核。 [TI Buck 功率级](https://www.ti.com/lit/an/slva477b/slva477b.pdf) · [ADI AN-149](https://www.analog.com/en/resources/app-notes/an-149.html) · [Infineon 线性 SOA](https://www.infineon.com/assets/row/public/documents/24/42/infineon-applicationnote-linear-mode-operation-safe-operation-diagram-mosfets-applicationnotes-en.pdf)

TI SLVA432 的控制模式表述有冲突。按精确控制器、调制方法和相应工况确定环路模型与检查线。相位目标作为选定系统的工程预算。Infineon 线性 SOA 文档页脚日期和文末参考时间不一致，保存实际 PDF，版本日期保持待定。 [TI SLVA432](https://www.ti.com/lit/pdf/slva432)

## 模拟、传感、基准和转换

1. 从传感器量程与源阻抗开始，逐级核共模、线性输出、摆幅/电流、过载恢复、前端保护、漏电和温漂。用最坏工况的保证值展开失调、偏置、参考、增益、驱动与校准后的误差。噪声统一输入或输出参考端，按有效带宽积分并处理相关项。
2. 对 SAR 分别验证采集窗口、源阻抗与开关电容回冲/R-C 稳定性、参考脉冲与码型。对 ΔΣ 检查数字滤波的群延迟、复用切换丢弃样本和事件相位。软件报告频率和输入通道阶跃后的首个有效码各自取证。稳态 1 LSB 预算不自动覆盖切换恢复。
3. 高阻、微弱信号和高分辨率通道重点检查回流、Guard/Kelvin、漏电、热电偶和测试夹具负载。保存负载和输入共模跃变、参考端、采样触发以及数据有效时间窗口，说明误差是否受温湿度、滤波、标定版本或仪器影响。 [TI 容性负载](https://www.ti.com/document-viewer/lit/html/SSZT999) · [ADI SAR 驱动](https://www.analog.com/en/resources/analog-dialogue/articles/front-end-amp-and-rc-filter-design.html) · [ADI 参考端 AN-931](https://www.analog.com/en/resources/app-notes/an-931.html) · [ADI ΔΣ AN-1265](https://www.analog.com/en/resources/app-notes/an-1265.html)

交接电路版本、测点网名、信号模式、器件文档版次、预算与剩余裕量、原始波形、测试条件。定量运行入口见 [工程预算](../../hardware/references/engineering-budgets.md)。
