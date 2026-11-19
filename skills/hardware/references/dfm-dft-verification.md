# 可制造性与可测试性核验

在 PCB/制造版本冻结时做 DFM，在布局和装配定版前做 DFT。前者核对设计数据、加工能力和制造证据，后者核对指定的故障是否能够被生产测试发现。两者使用同一板版次、叠层、装配变体和网络名称。

## DFM：通孔、环宽与错位

1. 从实际订单能力或已确认的工艺文件取得板材、层数、铜厚、成品孔/钻刀直径的定义、铜边界和尺寸公差。选择 PTH、NPTH、过孔、压入孔或槽孔的正确规则。嘉立创建议能力与绝对下限分开列，网站对不同工艺的说明也有区别。若概览值与具体选项不一致，以订单和 CAM 的确认值为准。 [嘉立创 PCB 制造能力，Holes / Traces](https://jlcpcb.com/capabilities/Capab)
2. 圆焊盘和圆孔可按几何下界 `w_min = (D_pad,min − D_hole,max)/2 − e_max` 筛查（均为 mm）。`e_max` 是对应层铜与孔可发生的相对径向偏心上界。先确认采用成品孔还是钻孔几何，形状有槽、泪滴或内层特殊结构时改用实际轮廓。公差应来自实际制造文件；若 CAM 判据已包含偏心或补偿，避免对同一误差重复扣减。
3. **原厂案例**。嘉立创通孔设计说明以最大 0.8 mm 引脚、1.0 mm 成品孔为例，下偏差 0.08 mm 时仍有 0.12 mm 直径余量。以名义环宽 0.25 mm 得焊盘 1.50 mm。该例说明名义和最坏尺寸的区别。钻偏后，最薄处可能靠近孔边，进一步偏移会导致破环。保留实际 CAM 回读和物理验收判据。 [嘉立创通孔焊接指南，孔径和环宽](https://jlcpcb.com/blog/through-hole-soldering-guide)
4. **合成反例**。1.60 mm 名义焊盘与 1.00 mm 名义孔给 0.30 mm 名义环宽。若项目分别给 1.58 mm 焊盘下界、1.13 mm 孔上界及 0.075 mm 偏心上界，实际下界为 0.150 mm，达不到项目要求 0.18 mm。换成 1.68 mm 焊盘下界后得 0.200 mm，同时复查铜间距、孔距和装配适配。项目也应独立验证最小成品孔与最大引脚之差，不能靠增大焊盘解决孔径过小。

```powershell
python -X utf8 scripts/engineering_validation.py annular-ring --pad-min-mm 1.58 --hole-max-mm 1.13 --offset-max-mm .075 --minimum-ring-mm .18
```

冻结记录使用实际交付文件的 Gerber／钻孔／机械数据、规则版本和对应证据。几何下界不足时暂停放行并回改尺寸或请 CAM 核实。还需检查孔铜、阻焊桥、塞孔、拼板、铜到板边及装配面；BOM/CPL 用同版同变体的装配预检。对实际工件，按项目认定的切片、测量或供应商工艺审核核对。 [IPC PCBA 标准指南，Production Cycle / Producibility Levels](https://www.ipc.org/sites/default/files/documents/PCBA-Checklist_0.pdf) · [制造放行](../../release-pcba-fabrication/SKILL.md)

## DFT：可达性、结构故障与功能覆盖

- **输入**。冻结 PCB 及变体、有效网表、BSDL、扫描链配置、测试点坐标、夹具/探针能力、测试程序版次、产品测试要求和故障清单。一项故障用稳定 ID 记录故障类型、位置、注入状态和证据。开路、短路、错料和功能边界按测试策略分别记录。同一个故障由 ICT、边界扫描、AOI 或功能测试同时覆盖时，在总覆盖中只计一次。
- **失效场景**。小间距 BGA 减少 ICT 的物理可达性，边界扫描仍可能覆盖部分互连。若工具把一个节点标为 `drive-only` 或 `shorts-only`，就不能据此把目标开路也记成已检出。Keysight 的节点级流程以前置网表、BSDL 与链验证区分这些状态。其工具资料还举了电源节点短路需在上电前排查的例子。 [Keysight，边界扫描覆盖分析](https://www.keysight.com/nl/en/use-cases/analyze-boundary-scan-test-coverage.html) · [Keysight 5992-1339，结构短路检查](https://www.keysight.com/us/en/assets/7018-05111/article-reprints/5992-1339.pdf)
- **量化验收**。分母为本版已审定的全部目标故障，`N`。已验证检出的数量是 `D`，证据未完成的数量是 `U`，确定遗漏保留在 `N`。覆盖率区间为 `100·D/N` 至 `100·(D+U)/N`。保守下界 ≥ 项目目标则该指标满足，可能上界仍低于目标则不满足，其余待验证。关键故障须按项目要求逐条给证据或批准处理。先留计划/分析覆盖与实际验证覆盖的身份，再从所需阶段的已确认事实归一化状态。

下面是合成故障清单。4 项已检出，1 项待验证，覆盖区间 80%～100%。项目目标为 90% 时结论待验证。如果最后一项确认漏检，上限变成 80% 且不满足。若漏检发生在 BGA 引脚，应修订测试路径或确认项目处置，不从分母删掉该故障。

```csv
fault_id,status
PWR_SHORT,detected
BUS_SHORT,detected
R21_OPEN,detected
J3_OPEN,detected
BGA_U3_PIN_OPEN,unknown
```

```powershell
python -X utf8 scripts/engineering_validation.py coverage --faults faults.csv --minimum-percent 90
```

用适合该故障的已知缺陷、故障注入、实际观察或经项目认可的仿真来关闭未验证项。交付故障清单及哈希、板版次、测试程序和夹具版次、实际覆盖类型、漏检清单与处置。指令执行和上电按台架权限办理。
