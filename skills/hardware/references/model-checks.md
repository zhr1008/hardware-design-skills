# 确定性工程验算

从 hardware 技能目录执行 `python -X utf8 scripts/engineering_checks.py evaluate --help`。既有 ADC/PDN 与工程核验子命令继续分别使用 [工程预算](engineering-budgets.md) 和 [工程核验](engineering-verification.md)。以下模型共用一个入口，以标准库计算。

**单点任务**可直接传参数。例如 1000 个同任务、相互独立的样本零失效，在单侧 95% 置信度下核目标概率 0.003。

```text
python scripts/engineering_checks.py evaluate --check zero-failure --assume-model iid_same_mission_zero_failures --bounded --input sample_count=1000 --input failure_count=0 --input confidence=0.95 --input target_probability=0.003
```

**重复验算**可用 `evaluate --file request.json`。最小记录如下。上下界表示可达的器件/系统角点时才写 `corners_reachable=true`，应保存其依据。精密十进制可用字符串输入。字段名附带单位，比例以 0–1 表示。模型声明由调用者根据当前工况提供，缺失时保留数值结果和待补内容。

```json
{"check":"divider-wcca","context":{"model":"positive_unloaded_linear_divider","inputs_bounded":true,"corners_reachable":true},"inputs":{"vin_min_v":10,"vin_max_v":10,"top_min_ohm":90,"top_max_ohm":110,"bottom_min_ohm":90,"bottom_max_ohm":110,"allowed_min_v":4.5,"allowed_max_v":5.5}}
```

| 子项及 context.model | 输入与模型边界 | 结论 |
| --- | --- | --- |
| i2c-pullup / open_drain_lumped_rc | vdd_max_v、vol_max_v、iol_min_a、rise_max_s、bus_cap_max_f、r_ohm、tolerance。30%–70% 单极开漏上拉，按器件模式和总线负载取值。 | 比较 (VDD−VOL)/I 与 tr/(0.8473·Cb) 及实装阻值区间。窗口冲突须核角点可达性，缓冲器和漏电另审。 |
| divider-wcca / positive_unloaded_linear_divider | 上例给全部字段。正电阻、非负输入、无负载分压，单调求极值。 | 对照允许闭区间，依赖条件未知的部分交叠返回待定。 |
| hot-copper / uniform_dc_copper_at_known_temperature | length_mm、width_mm、finished_copper_um、current_a、copper_temp_c、rho20_ohm_m、alpha_per_k、contact_ohm、maximum_drop_v。均匀成品铜、已知铜温、直流。 | R(T)=ρL/A·[1+α(T−20)]，分别报总压降、铜及接点功耗。温升、颈缩和孔分流另审。 |
| measurement-guardband / expanded_interval_inclusive_limits | value、expanded_uncertainty、coverage_probability、unit、minimum、maximum。量与范围同单位，输入已按约定覆盖概率扩展的不确定度。 | 测量区间全在闭合规格内通过，全在外越界，交叠待定。采用项目批准的判定规则。 |
| stencil-ratio / rectangular_straight_wall_aperture | length_mm、width_mm、thickness_mm、minimum_area_ratio、minimum_aspect_exclusive。矩形直壁及实际工艺限值。 | 开口/侧壁面积比须 ≥ 指定值，短边/厚度须 > 指定值，同时报体积。交装配厂核 SPI 转移与工艺能力。 |
| zero-failure / iid_same_mission_zero_failures | sample_count、failure_count、confidence、target_probability。整数 n>0，实际失效数为零，试验任务相同且独立。 | 单侧上限 1−(1−confidence)^(1/n)。样本不足以支持目标时待定。 |
| tolerance-stack / linear_signed_interval_stack | nominal、signed_contributions（有符号的 [下界,上界] 列表）、minimum、maximum、unit。线性尺寸链，按同一方向与单位。 | 包络完全超规格可判失败；部分越界先核同时可达，未证实则待定。 |
| s-passivity / normalized_power_waves_equal_real_z0 | reference_ohm 为两端相同、实数正参考阻抗；samples 每项含 hz 及 2×2 的 s，行=出端口，列=入端口，每项 [实部,虚部]。 | 逐频检 I−SᴴS 的半正定性，含耦合交叉项。任一违反即给出频率。结果覆盖所给频点，其他频点、因果性和夹具拟合须另查。 |

退出码 0、1、2 分别表示在报告的范围内通过、已证明越界、条件不足或输入无效。旧 CLI 可接受 `--context FILE` 校对返回的模型标识和 `inputs_bounded`。单点输出在当前模型内使用。正式审查另绑定该版本器件、工件、来源锚点及原始输入，按证据外壳记录计算阶段。复算的几何、采样点和置信上限只交接各自证据范围。

出处与适用条件参见 [NXP UM10204 §7.1](https://www.nxp.com/docs/en/user-guide/UM10204.pdf)、[ECSS WCA 手册](https://ecss.nl/wp-content/uploads/handbooks/ecss-q-hb/ECSS-Q-HB-30-01A14January2011.pdf)、[TI SLUA271C §4](https://www.ti.com/lit/an/slua271c/slua271c.pdf)、[ILAC G8](https://ilac.org/publications-and-resources/ilac-guidance-series/) 和 [IBIS Touchstone 规范](https://www.ibis.org/specs/)。文件格式与被测对象、频率、波基准和参考阻抗须对应。
