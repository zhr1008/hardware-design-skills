# 板材、机电装配与环境可靠性

## 叠层与特种板材

由板厂确认压合后的层厚/公差、成品铜厚、材料构造、Dk/Df 的频率和测试法、阻抗、过孔类型、压合和替料窗口。标注参考平面、残桩/背钻、过孔回流、铜分布与热点。压降按最小截面和实际温度核，温升使用适用的板结构、热路及试验。[AMD 叠层设计](https://docs.amd.com/r/en-US/ug583-ultrascale-pcb-design/PCB-Stackup-and-Layer-Order) · [IPC-2152 公开目录](https://www.ipc.org/TOC/IPC-2152.pdf)

| 板型 | 审查与交付 |
| --- | --- |
| 普通或高 Tg FR4 | 确认任务温度、吸湿、耐回流、CAF/CTI 和使用等级。分开存 DSC、DMA、TMA 的 Tg 与 Td、Z 轴 CTE、T260/T288、长期 RTI。FR408HR 数据中的 DSC 190 °C 和 DMA 230 °C 对应不同试验定义。 |
| 低损耗高速/RF | 向厂商取指定频率与构造下的设计 Dk/Df、玻纤/树脂量、铜箔粗糙度与公差。RO4350B 的 Process Dk 与 Design Dk 分开使用。 |
| 厚铜和复杂过孔 | 最小成品铜厚、电流和热点、蚀刻补偿、树脂填充/压合、孔铜、孔径环宽、层对准与填孔封帽共同确认。 |
| 铝基 IMS | 电气、热和结构联合确认绝缘层厚度/介电强度/工作电压、可能的局放、铜到铝界面热阻及金属基底、紧固件和端口的接地或隔离。 |
| 软板、软硬结合 | 分静态成形与动态弯折，规定铜类型、叠层、中性面、弯折方向和半径、循环和温度、补强和过渡区，在弯折区评估过孔、焊点、器件及刚性边缘。小变形 `ε≈y/Rb` 可做量级初筛，实际寿命由构造、方向、次数与试验确认。 |

2026 新发布目录可定位 IPC-2223F 与 IPC-4204C，历史修订表仍可显示 2223E。以项目批准的对应正文、板厂构造和生产样件为判定依据。 [Isola FR408HR](https://www.isola-group.com/wp-content/uploads/data-sheets/fr408hr-laminate-and-prepreg.pdf) · [Rogers RO4350B](https://www.rogerscorp.com/advanced-electronics-solutions/ro4000-series-laminates/ro4350b-laminates) · [IPC 新发布目录](https://www.electronics.org/recently-released-ipc-standards-and-documents)

## 公差、板弯及夹具

- 锁定 ECAD/MCAD 原点、正反面、单位、旋转和装配状态。对外壳、连接器、灯、按钮、线束、螺钉和垫片检查最大包络、插合和过行程、操作维修空间及装配时施力路径。STEP 名义几何后还要带入尺寸与形位、公差、焊后高度、翘曲、热变形及动态位移。 [ISO 1101 的公开范围](https://www.iso.org/standard/66777.html) · [TE 114-161733 浮动与配合条件](https://www.te.com/content/dam/te-com/documents/consumer-devices/global/product-spec-114-161733.pdf)
- 线性小位移时用 `g_min=g0−Σ|si|ti` 检查间隙。最坏角落需可达，统计分析需有实际分布和相关性。结果区间跨限且无可达违例时保留待验证。安全间隙同时纳入螺钉偏移、内层铜和装配垫片。
- 记录分板、插拔、锁螺钉、压床、搬运的装配夹具、板支撑及实测主应变、方向和应变率。简支小挠度梁的 `6tδ/L²` 只估量级。实板各向异性、槽孔和器件刚化会改变局部应变。IPC-TM-650 2.4.22C 是 PCB 弓曲和扭曲的测量方法，IPC/JEDEC-9704A 用于板级应变。采购对应的材料/封装资格包络，记录具体工序。 [IPC-TM-650 2.4.22C](https://www.ipc.org/sites/default/files/test_methods_docs/2.4.22c.pdf) · [IPC/JEDEC-9704A 公开目录](https://www.ipc.org/TOC/IPC-9704A.pdf) · [Murata 板弯防裂示例](https://article.murata.com/zh-cn/article/layout-helps-prevent-chip-mlcc-from-cracking)

## 涂覆、环境与联动复测

- 涂覆和灌封先查连接器、测试点、天线、传感器口、晶振和散热面的禁涂限制。指定清洁度、厚度/边缘、空洞、材料/批次、固化、模量、CTE、返修及实际热接触。特殊器件遵守其原厂工艺条件。可能改变爬电/间隙的材料及过程依受控条款单独认可，复测耐压、热与功能。 [IEC 60664-3 的公开范围](https://webstore.iec.ch/en/publication/26148) · [TI SWRS278B §11.6](https://www.ti.com/lit/ds/symlink/cc2651r3sipa.pdf) · [NDK 工艺注意事项](https://www.ndk.com/en/products/info/post_39.html)
- 区分温度/湿热/冷凝/温循、正弦振动/冲击/随机振动、运输与实际通电、进水与长期密封。定义任务剖面的轴向、频带/PSD、夹具、严酷度和复测判据。随机振动的 `grms=√∫PSD(f)df` 仅在相同积分约定下可比，谱形及安装模态共同决定响应。IEC 60068-2-64 的 2026 Ed3 取代 2008+A1:2019，旧搜索摘要单列。低温、干热和恒定湿热各有 2025 版。用正式采用版定试验。 [IEC 随机振动](https://webstore.iec.ch/en/publication/117312) · [低温](https://webstore.iec.ch/en/publication/82354) · [干热](https://webstore.iec.ch/en/publication/82355) · [恒定湿热](https://webstore.iec.ch/en/publication/109062)

交付同版板图、外壳和装配模型、工艺及夹具、坐标和包络、公差和热模型、板弯及量测点图、涂覆/环境试验原始证据和结果。变更树脂、支撑、扭矩、导热垫或板材后复核相关热路、隔离与机械适配。

## 从板型选择到首件验证

1. **先锁工作叠层。** 如果高频阻抗满足、插损预算不足，分别查铜粗糙度、材料 Df、厚度和过孔损耗，再比较低损耗材料与减少换层。只凭 `Dk` 名义值选成品板会漏掉构造、频率和板厂代料。向制造交同一版的成品厚度、蚀刻后宽度、阻抗容差和测试 coupon 布置。阻抗和成品几何有偏差时，回到实际压合和铜厚，不直接套标称层叠。
2. **分开检验静态包络与施力工序。** 合成机壳的间隙名义 0.8 mm，焊后高度、板支撑、壳体和热变形相对间隙贡献分别为 `±0.20`、`±0.15`、`±0.18`、`[-0.12,0]` mm，包络下界 0.15 mm。若项目要求至少 0.20 mm，没有已证同时可达的负角点时先记待验证。复用 [`tolerance-stack`](../../hardware/references/model-checks.md)，再以同基准实测装配及热态位移。夹具加支撑能降低压装板弯，但还需复核底面器件和弯折区。
3. **把工艺变更当作多域变更。** 软板弯折区变薄可能增大电阻、改变阻抗及移动中性面。涂覆可能影响散热、射频及爬电资格。换黏合剂或导热垫会改变装配高度和热循环应变。每次变更列受影响的板材、力学、热、隔离及工艺检验。首件核实际截面、尺寸和关键工序应变，环境阶段核长期失效，分别记录。
