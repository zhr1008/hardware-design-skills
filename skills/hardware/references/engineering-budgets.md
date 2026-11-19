# ADC 前端与 PDN 预算

先明确当前板版次、完整器件型号、工作条件与验收限值。从仓库根目录运行以下离线命令。保存实际输入和 JSON 结果，分别记录计算、仿真、原生检查和实测的覆盖。

## SAR ADC 前端

1. 查该 ADC 的输入范围、共模、最短采集窗 `t_ACQ` 和切换时序。按输入波形或最坏通道切换确定有效阶跃 `ΔV_step`。建立误差预算 `V_err,budget` 来自当前项目，预留噪声、增益、失调和基准误差。采样周期与实际采集窗分别记录。
2. 用等效 `R` 与 `C` 列出一阶近似。线性单极点的残余误差为 `|ΔV_step| exp(-t_ACQ / τ)`，其中 `τ = RC`。在阶跃幅值大于预算时，`τ ≤ t_ACQ / ln(|ΔV_step| / V_err,budget)`。若阶跃已落在预算内，本模型对 `τ` 无额外上限。R 以 Ω、C 以 F、时间以 s、电压以 V。
3. 核对模型漏项。ADC 回冲、通道切换、源阻抗、运放压摆和输出稳定、偏压后外部电容、噪声带宽及引脚寄生都可能改变结果。参考端的动态负载、驱动能力和去耦独立按所选器件手册核对。仿真使用实际采样时序及可核的开关电容或原厂模型。
4. 交给 PCB 的约束含驱动与 ADC 相对位置、滤波与参考支路、回流路径和测点。台架用同一输入阶跃、切换序列、带宽、采集时刻与判据复测，并标明采样设置和板版次。

```powershell
python -X utf8 skills/hardware/scripts/engineering_checks.py adc-settling --step-v 2 --acquisition-s 1e-6 --error-budget-v 0.0005 --resistance-ohm 1000 --capacitance-f 100e-12
```

这个合成用例得 `τ=100 ns`，模型允许上限约 `120.6 ns`，残余约 `90.8 µV`。返回 `within_model_budget` 时，可进入实际工况复核。返回 `exceeds_model_budget` 时，先核输入和近似的适用性，再排查滤波、驱动和采样设置。

来源：[ADI 精密 SAR 前端 RC 指南，采集建立和多路切换](https://www.analog.com/en/resources/analog-dialogue/articles/front-end-amp-and-rc-filter-design.html) · [ADI AN-931，参考端和驱动的器件条件](https://www.analog.com/en/resources/app-notes/an-931.html) · [ADI SAR 输入模型说明](https://www.analog.com/en/resources/technical-articles/ltspice-simulating-sar-adc-analog-inputs.html)

### 对照原厂算例，确认采集窗与阶跃

TI SBAA256B 的无缓冲慢速采集例用 `R_TH=10 kΩ`、`C_FLT=680 pF`，得到 `τ=6.8 µs`，按其近似 `11τ` 得 `74.8 µs` 的最小采集时间。对应 ADS7056 数据表 §9.2.3 表 5 中，两种配置同为 10 kSPS。SCLK 为 0.24 MHz 时采集窗只有 25 µs，60 MHz 时为 99.7 µs。以合成的 3.15 V 全输入阶跃、100.5 µV 预算复算，一阶残差分别约 79.7 mV 和 1.35 µV，只后者满足该模型预算。SBAA256B 表 1 的 36.24 µV 是另一项直流输入回冲仿真，该表未提供对应瞬态误差的实测值。 [TI SBAA256B 表 1 与第 2 页](https://www.ti.com/lit/an/sbaa256b/sbaa256b.pdf) · [ADS7056 数据表 §9.2.3 表 5](https://www.ti.com/lit/ds/symlink/ads7056.pdf)

ADI 的 AD7980 前端例则先估单通道正弦信号在转换窗内的变化，再用采样电容和外部电容估算重新接入时的回冲阶跃。多路复用时还要核对实际切换顺序、最坏通道差以及驱动器的大信号建立和稳定性。评审时在输入证据里同时保留采集窗的起止事件、阶跃的测点以及预算单位。若只知道标称采样率，或把原厂应用例的回冲阶跃代入本项目的多路切换，应保留建立时间为待验证。 [ADI 精密 SAR 前端 RC 指南，公式 1–7 与多路复用章节](https://www.analog.com/en/resources/analog-dialogue/articles/front-end-amp-and-rc-filter-design.html)

## PI/PDN

1. 确定电源轨、工作点和负载阶跃 `ΔI`（A）。从允许的轨电压偏差中为动态压降分配 `ΔV`（V），注明直流误差、测量裕量和其它预算。用 `Z_target = ΔV / ΔI`（Ω）定义指定范围内的平坦初筛目标。频带按项目或目标器件、负载频谱和供电路径核定。
2. 对照实际 VRM、安装位置、安装电感、PCB 平面和走线、有效电容、ESR、ESL 以及封装级影响。直流压降与动态阻抗各自检查。并联混合去耦时关注反谐振，结合负载附近的返回路径和实际可量测端口判断。
3. 给布局专项电源网名、板层和区域、供电与去耦位置、关键路径与测点。评审记录预算来源、板版次、模型或测量条件、采样跨度与超限点。怀疑狭峰时补采点或检查输入模型，测量与仿真分别留身份。

```powershell
python -X utf8 skills/hardware/scripts/engineering_checks.py pdn-target --delta-v 0.03 --delta-i-a 0.6 --fmin-hz 1000 --fmax-hz 1000000
python -X utf8 skills/hardware/scripts/engineering_checks.py pdn-target --delta-v 0.03 --delta-i-a 0.6 --fmin-hz 1000 --fmax-hz 1000000 --sweep measured.csv
```

脚本将合成预算算成 `50 mΩ`。扫频 CSV 表头为 `frequency_hz,impedance_ohm`，每行是唯一频率及对应阻抗幅值，编码为 UTF-8。脚本报告频带内采样点、缺失的端点、最大采样值、超限点及源文件 SHA-256。端点明确采到且所有带内点满足目标时，输出 `within_sampled_points`。带内已观察到超限时输出 `sample_limit_exceeded`，缺少端点且未观察到超限时输出 `sample_coverage_incomplete`。采样点之间的狭峰需要足够的扫频分辨率或其它证据。

来源：[TI SWPA222A 第 4 节，目标阻抗与频率范围](https://www.ti.com/lit/an/swpa222a/swpa222a.pdf) · [AMD UG863，目标阻抗与安装电感](https://docs.amd.com/r/en-US/ug863-versal-pcb-design/Target-Impedance) · [AMD UG583，去耦反谐振](https://docs.amd.com/r/en-US/ug583-ultrascale-pcb-design/Capacitor-Anti-Resonance)

### 从目标阻抗筛查走到放行

预算先统一电压和电流的定义。AMD UG863 的 Versal 示例从 0.80 V 电源轨的 ±3% 容差中分出 ±1% 直流误差和 ±2% 交流纹波，以 40 A 阶跃计算出 0.40 mΩ。Altera AN-750 表 1 的另一种给定方式是最大电流与瞬变百分比，例如 `0.9 V × 5% / (30 A × 50%) = 3 mΩ`。使用实际器件文档或需求的动态预算与阶跃定义，明确单边幅值、峰峰值和直流误差分配。在同一验证中同时保留频域目标和实际负载时域限值。针对共用电源轨，按工作模式记录各负载的并发关系。 [AMD UG863 目标阻抗示例](https://docs.amd.com/r/en-US/ug863-versal-pcb-design/Target-Impedance) · [Altera AN-750 §1.4](https://docs.altera.com/r/docs/683155/current/an-750-using-the-altera-pdn-tool-to-optimize-your-power-delivery-network-design/calculating-ztarget)

只验端点会漏掉反谐振。一个合成的并联 RLC 取 `R=80 mΩ`、`L=1 nH`、`C=1/((2π·1 MHz)²L)`。用 `Z=1/(1/R+j(2πfC−1/(2πfL)))` 生成样本。只输入 0.9 MHz 和 1.1 MHz 时，最大采样值约 30.4 mΩ，脚本对 50 mΩ 目标报告 `within_sampled_points`。补入 1 MHz 后得到 80 mΩ，报告 `sample_limit_exceeded`。审核应结合阻抗曲线、疑似峰值频段以及所用频率步进读回数据。只有粗采样时，连续频带结论留为待验证。 [AMD UG583 反谐振](https://docs.amd.com/r/en-US/ug583-ultrascale-pcb-design/Capacitor-Anti-Resonance)

读取实测扫频时记录供电状态、参考面、夹具、校准及覆盖。毫欧级双端口并联测量需要核对接地环路和夹具寄生，限值附近还要考虑测量不确定度。时域验证另记录实际负载的跃变量、边沿、保持时间、欠冲、过冲及恢复时间，并按该轨的产品判据判定。 [Keysight 5989-5935，低阻抗与夹具影响](https://www.keysight.com/fi/en/assets/7018-08474/application-notes/5989-5935.pdf) · [AMD UG583 优化去耦网络](https://docs.amd.com/r/en-US/ug583-ultrascale-pcb-design/Optimum-Decoupling-Network-Design)

## 交给下一阶段的证据

| 交接 | 保留字段 |
| --- | --- |
| 器件及原理图交 PCB | 完整型号与手册版次、网络或位号、工况、预算来源、计算输入及关联系统版次。 |
| PCB 交仿真及台架 | 叠层、工件版本、端口或测点、采集设置、模型覆盖和原始文件。 |
| 综合评审 | 使用对应的测试和判据分别给出结论，保留工件身份、模型假设、实测条件和待补证据。 |

退出码 0 表示算出预算或所检样本满足，1 表示已证越界，2 表示样本覆盖不足或输入无效。频点覆盖见专项状态，正式交接记录实际测量窗口。
