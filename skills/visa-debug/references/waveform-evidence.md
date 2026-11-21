# DS1054Z 屏幕波形证据

向 [bench-check](../../hardware-design-review/references/bench-results.md) 提交单值前，保留原始响应及读回设置摘要，记录聚合窗口、板号、硬件版次、固件及测量链。缺少前导时保留原始响应与缺项。

离线函数 `scripts/waveform_readback.py` 中的 `decode_screen_waveform` 接收原始 DATA 响应、同次采集的前导和实际读取设置。型号限定为 RIGOL DS1054Z，输入范围是 `CHAN1` 至 `CHAN4`、`NORM`、`MAIN`（YT 时间模式）、`VOLT`、`BYTE` 或 `ASC`。使用 `*IDN?` 和仪器读回确认这些值。原厂手册 PGA19108-1110 的 2-15、2-157、2-217 至 2-226 定义单位、模式、数据和前导。 [RIGOL 编程手册](https://www.rigol.com/dam/global/downloads/brochures/en/program-guide/oscilloscopes/DS1000Z_ProgrammingGuide_EN.pdf?t=1760982668513)

- BYTE 按 TMC 数据头的长度读取无符号码值，用 `(code - YORigin - YREFerence) × YINCrement` 换算为 V。ASC 响应已经是物理电压，直接读取有限数值。
- 屏幕首点索引为零，`XREFerence` 为零，用 `XORigin + index × XINCrement` 得到秒。采集窗口须从第一个点开始，读回的末点、前导点数和响应点数相符。前导也须有同格式、同模式以及有限有效的比例和偏移。
- 缺元数据、点数、格式、单位、设置或时间轴证据时保留原始字节与失败原因，按未定标证据处理。原始响应、前导和读回设置应可追溯到同一采集操作。若现场采集改变了仪器传输设置，记录采集前后的设置、恢复动作和恢复读回。
- `NORM` 取屏幕显示波形。样点间距取屏幕时基，不能从中认定完整采集存储、原生采样率、短脉冲或峰值已覆盖。仪器给出的单位和比例还需结合实际探头、接法、信号链和校准记录确定测量适用范围。
