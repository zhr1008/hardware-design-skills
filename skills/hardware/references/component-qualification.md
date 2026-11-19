# 器件资格与替换验收

按项目/采购文件的要求核对完整订购号、原厂、封装、适用生产配置和资格依据。将资格覆盖、实际电气工况和供应保证分别核验。本页的公开型号只用于说明如何读原厂证据。

## 一手依据及适用条件

| 证据 | 需核实的内容 |
| --- | --- |
| AEC-Q100 集成电路 | Rev J（2023-08-11）§1.3.1–1.3.4 明确供应方资格与应用批准的角色；表 1 的温度等级是环境工作范围。§2.4 及附录 1 约束族数据使用，第 3 节和表 3 处理工艺变化的验证。审核订单实际采用的标准版次及原厂数据。 [AEC 原文 Rev J，原件镜像](https://www.guerrilla-rf.com/includes/pdfs/general/AEC_Q100_Rev_J_Base_Document.pdf) · [TI 原厂汽车资格说明](https://www.ti.com/en-us/quality-reliability/faqs) |
| AEC-Q200 无源件 | Rev E（2023-03-20）§1.1 区分既往资格、新资格和变更。§2.3、附录 1 允许按测试项目有理由地选用资格族数据。陶瓷电容看表 2 系列，电阻看表 7 系列，检查封装、材料、工艺与相应测试的适用范围。原厂给明确版次和入族映射后，再由项目复核是否可用。 [AEC 原文 Rev E，原件镜像](https://www.icecomponents.com/wp-content/uploads/2024/09/AEC_Q200_Rev_E_Base_Document.pdf) |
| 原厂订单号和工艺变更 | 一份型号报告能够给出订购身份、试验项与结果来源。TI 对 `TPS92602QPWPRQ1` 的 2025-03-25 资格摘要 2–3 页含环境、寿命和电气验证条目，部分结果要求转查器件数据表。TI PCN 20230306002.2 说明即使物料编号未改，晶圆厂、封装地点和键合材料也可能有变化。以受影响列表、物料实际范围和对应资格结论决定是否回流评审。 [TI 资格摘要](https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/196/TPS92602QPWPRQ1.pdf) · [TI 变更通知](https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/196/0564.PCN20230306002_2D00_1.pdf) |

2026-11-19 的独立研究记录从 AEC 发布方 HTTP 原件读取 Q100 Rev J1（2026-03-24）表 1、§1.3/§2.4，以及 Q200 Rev E §1.5/§2.3。主会话复访官网有代理拒绝或超时，工程参考手册也记录官方访问受限。Q100 J1 的 Grade 0/1/2/3 环境工作温区分别为 −40 至 150/125/105/85 °C。项目使用时重新留存实际原件及哈希、客户指定版次、器件保证工况和原厂覆盖声明。J 版历史资料继续按 J 版引用，Q101 与 GJB 缺受控正文的条款保持待核。 [AEC 官方目录](http://www.aecouncil.com/AECDocuments.html) · [Q100 Rev J1 官方原件](http://www.aecouncil.com/files/Documents/AEC%20Q100-Rev%20J1.pdf) · [Q200 Rev E 官方原件](http://www.aecouncil.com/Documents/AEC_Q200_Rev_E_Base_Document.pdf)

## 典型误判与可复算反例

**版本和试验条件反例。** Murata 的个别规格 `GCM3195G2A182JA16-01A` 第 2 页明确标注 Q200 Rev D。第 4 页的 3 mm 板弯数据对应规定试板、跨距/受压方式和保压时间；项目装配形变要在自己的板和工况上验证。同文档的 100 V DC 额定值与耐压试验的 250% 条件分别用于使用和应力试验。以该试验条件计算为 250 V，同时保留 100 V 的器件额定值。若项目要求 Rev E，查受控合同是否接受 Rev D 及原厂补充报告，不能按当前产品网页的系列说明改写报告版次。 [Murata 个别规格，第 1、2、4、6 页](https://pim.murata.com/asset/pim4/ceramicCapacitorSMD/GCM3195G2A182JA16-01A-EN_PDF_CERAMICCAPACITORSMD?lastModifiedDatetime=20250813121625)

- **把温度等级当作整机温度裕量。** 合成项目最坏器件周围空气温度为 102 °C，取 ±4 °C 温度验证区间，并用项目认可的保守决策规则。区间上界为 106 °C。若证据只覆盖 Q100 Grade 2 的 105 °C 环境上限，这一项为待验证；若同一实际订购型号已证实覆盖 Grade 1 的 125 °C，环境温度这一项保守裕量为 19 °C。仍须判断冷端、实际结温及型号在目标供电、频率、温度和负载下的保证值。 [AEC-Q100 Rev J，表 1](https://www.guerrilla-rf.com/includes/pdfs/general/AEC_Q100_Rev_J_Base_Document.pdf)
- **料号一致就跳过变更，或用系列名替代资格覆盖。** 上述 PCN 为实际制造配置变更。项目评审须建立受影响的订购号与生产配置映射、核变更日期与接受条件；用途涉及绝缘、功率或引脚时，把材料、封装、热与装配变化回流给对应专项。Q200 同封装和容值不能支持不同制造商或材料工艺之间借用资格。实际电容偏压、纹波温升、浪涌、老化和板弯风险由对应的数据和板级验证处理。 [AEC-Q200 Rev E，§2.3 与附录 1](https://www.icecomponents.com/wp-content/uploads/2024/09/AEC_Q200_Rev_E_Base_Document.pdf)

```powershell
python -X utf8 scripts/engineering_validation.py limit --direction max --value 102 --uncertainty 4 --limit 105 --unit degC
python -X utf8 scripts/engineering_validation.py limit --direction max --value 102 --uncertainty 4 --limit 125 --unit degC
```

## 放行与证据回流

对本版每一项必需资格记录 `项目规格/限值 → 完整 MPN 与封装/配置 → 报告版次、页码及实际覆盖 → 工程工况 → 结论`。按应用剩余项逐项检查下列证据。

1. 资格文件覆盖所有订单允许的配置，或有原厂签发的家族映射与项目接受依据。对应测试条件、批次/样本数和结果与该类器件的适用条款、项目要求逐项闭环。记录变更资料与特殊批准。旧版仍可使用的条件从项目合同和对应标准获得。
2. 电气指标在项目最坏工况满足：以数据表保证值核温度与电压边界，验证瞬态、SOA、寿命和应用降额。偏压/公差下的有效电容、功率电阻或磁件温升按器件和实际使用复核。
3. 批次与渠道证据分别留存。变更、例外或证据缺项标待审。替代或 PCN 触及功能、封装或制造约束时，刷新资格锁定、BOM、库与制造交接并复验。

项目通过条件来自采购文件及批准的工程限值。资格报告的摘要、渠道标签、测试方法编号或计算通过的单项温度结论只覆盖各自字段；资格锁定脚本检查表内证据和状态，仍需评审者取得对应原文。 [采购资格专项](../../qualify-pcba-sourcing/SKILL.md)
