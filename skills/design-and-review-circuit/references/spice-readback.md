# ngspice 批处理与量测

```powershell
python -X utf8 -B scripts/run_spice.py assets/spice-fixtures/rc.json --output-dir path/to/new-run --ngspice-cli path/to/ngspice
```

输入 `hardware-spice-input-v1` 由同目录网表、模型文件名和量测限值组成。每个小写量测名与网表中唯一一条 `.measure` 或 `.meas` 对应，提供单位和至少一个数值限值。保持模型许可证与适用工况的项目记录。网表和显式列出的模型复制到新目录，以 `-n -b` 调用 ngspice。支持同目录 `.include`，批处理不加载用户配置或执行控制脚本。

结果遵从[证据包络 v1](../../hardware/assets/evidence-envelope.schema.json)。记录原始输入、模型与日志 SHA-256、已读回温度和求解选项、量测定义、求解器版本及限值。退出码 0 表示量测限值成立，1 表示量测超限，2 表示缺少量测、工具故障、超时或输入无效。量测单位沿用输入合同，核对前确认网表表达式和阈值使用该单位。

[夹具](../assets/spice-fixtures/rc.json)包含可用 `R × C` 独立算出的 1 ms RC 回归。另有[不可达量测](../assets/spice-fixtures/rc-missing.json)及[缺模型](../assets/spice-fixtures/missing-model.json)。结果只覆盖本次模型、激励和工况。波形导出、极限覆盖与硬件验收留在对应评审步骤。

[串联 RLC](../assets/spice-fixtures/rlc.json)以 1 V 阶跃测电容两端的欠阻尼峰值与后段稳定值。对 100 Ω、10 mH、100 nF，`α=R/(2L)=5000 s⁻¹`，`ωd=√(1/(LC)−α²)≈31225 rad/s`，阶跃后的首峰约在 100.6 µs，解析峰值 `1+exp(−απ/ωd)≈1.605 V`。网表使用 1 ns 上升沿及 1 µs 最大步长，测试独立复算该解析值。带饱和、非线性损耗和复杂激励的实际电路应另用适用模型。

通过总入口可调用 `hardware_tool.py spice-run <实验 JSON> --output-dir <新目录>`。固定批处理用于已核对的网表与模型。对陌生网表，先检查 `include` 依赖、外部输入和求解器特有指令，再决定是否运行。交给其他专项时保留量测定义、限值和原始日志，使用[正式检查证据](../../hardware/references/evidence-and-backends.md)重新核对工件摘要。

[ngspice 批处理文档](https://ngspice.sourceforge.io/ngspice-control-language-tutorial.html)
