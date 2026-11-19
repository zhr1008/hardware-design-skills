# 工程知识的来源索引与核对

规则卡回答要检查什么，原件回答要求来自哪里，项目工件回答当前板是否达到要求。三者都要有独立的身份与定位。先用 [工程域索引](lifecycle-domain-index.md) 定位专项，再按需要读规则、项目原件和对应版本的标准。

从 hardware 技能目录运行 `python -X utf8 scripts/knowledge.py sources AN2867` 可同时查规则书目、手册条目和制造修订记录。输出含来源集合、版本与原始访问限制。精确来源 ID 优先，`--limit` 控制本次返回量。

## 两套本机索引的合流

| 入口 | 数据与定位 | 使用方式 |
| --- | --- | --- |
| `hardware` 的 [公开审查规则](../assets/review-knowledge/rules.json) | 96 条条件规则，26 个书目 ID，120 个引用。每处 `document_id + pdf_page` 指向编卡时的原件，`printed_page` 为可选印刷页。 | `knowledge.py rules --summary` 后按 `--id` 取规则及来源。公开包含书目、校核状态和可公开入口。 |
| `hardware` 本机工程资料库 | `assets/engineering-library/manifest.json` 的 `LIB…/DOC…` 文档，`scripts/index.db` 的 PDF 物理页或段落，必要时用受控原件复核。 `page-labels.json` 以原件哈希绑定印刷页。 | [工程资料检索](engineering-knowledge.md) 中的 `find` → `search --doc` → `read`。本机安装的脚本可直接读同目录论证资料，仓库脚本用 `--library` 读取同结构的本机库。 |
| `hardware-design-review` 本机扩展知识库 | `references/00-evidence-source-governance.md` 的治理、`92-rule-registry-index.md` 的精炼规则、`90-raw-source-catalog.md` 与 `sources/source-manifest.json` 的 `RAW…/PROJECT…` 及行段校验。 | 在已安装且含本机扩展的技能目录运行 `python -X utf8 scripts/query_kb.py "关键词" --scope curated --max-hits 6 --context 2`，按源 ID 缩小结果再读取 `raw` 行段。公开副本的通用 [实测验收](../../hardware-design-review/references/bench-results.md) 也可独立使用。 |

两套编号分别以原件和提取片段为基准。跨库先比标题、语种、版本、完整原件哈希，再比章节、页标与语义。RAW 的 SHA-256 保证归档文本或行块的完整性，页索引的 SHA-256 指向 PDF 字节。源 ID 通过下表互相发现。核对正文时保留两套原生定位。合并本机书目字段时使用完整原件哈希匹配，保留本机目录和原件路径。

| 页索引 | 行段索引 | 适用边界 |
| --- | --- | --- |
| `LIBD9CD19BAB8D156E0` 开关和基准源、`LIBCDDA9602541036D3` 信号链噪声、`LIBB0463C6DB85D0C6D` 看数据手册 | `RAW12-S009`、`RAW12-S014`、`RAW12-S017` | 同题发现入口，逐篇核文档号及物理页。 |
| `LIB6E8985C91043D6A9` 无源器件、`LIBEE21AAFB7FF12E57` 电路问答、`LIB883B9DE45BA637F7` Power 问答 | `RAW12-S020`、`RAW12-S023`、`RAW12-S013` / `RAW18-S009` | 同题发现入口。两处 Power 问答可能来自同一版本，引用时防止重复计数。 |
| `LIBFD48B4A7B874BF08` IPC-7351B CN、`LIB6A1E6646C5340E78` J-STD-033A、`LIBAAB1225C22702881` IPC-2221B | `RAW13-S004`、`RAW13-S007`、`RAW13-S001` | 前两项为标题候选，须确认译本与原件页。IPC-2221 中文提取段不能标作 2221B 英文原件。 |
| `LIBA56469486BFACE53` 运放指南、`LIBD3F1DB5447640381` 电子学的艺术上册 | `RAW15-S001`、`RAW15-S002` | 行档录有提取范围与缺页线索，扫描页用本机 OCR 找原页，精确公式、图和单位需读 PDF 图像。 |
| `LIB7FB74BD8F857807A` SBOA269B | `RAW18-S002` | 两边的文档号和题名对应。引用官网 PDF 物理 1、2 页时用对应的版本，RAW 行段编号另存。 |

本机扩展含其他来源与内部项目基线。项目资料只在本地按项目授权检索和引用。行段条目点出工程适用性后，用当前项目事实和受控要求确认，历史精炼条目中未经来源化的固定阈值作为筛查。旧版或扫描质量低的资料可用来解释机制和追查相关原件。

## 公开来源的状态

| 字段或值 | 能据此引用的内容 |
| --- | --- |
| `source_sha256` | 规则物理页所绑定的原件。允许与本机清单和已获取的 PDF 比对。 |
| `verified_same_pdf` | 官网取回文件与所引 PDF 的 SHA-256 相同，核对页位置可以直接使用。滚动 URL 再次下载后重验版本与哈希。 |
| `verified_same_edition_locators` | 已在官网正文对照相应版本、印刷页与引用物理页。当前记录按页核验。 |
| `pagination_unverified` | 公开正文可查，引用段的公开页码尚待对应。线上引用重新定位文字、图表或章节。 |
| `metadata_only` | 目录、索引摘要、发布帖或有访问限制的同版入口。可用于识别来源。条文需另读。 |
| `version_conflict` | `related_official_url` 和 `source_url_edition` 指明新版本、其他语言或其他编排。现有页码绑定原件所列版次。 |
| `unknown` | 未找到可定位本版的公开入口。如有 `related_official_url`，仅用于另查工程主题。 |

`access_status` 只反映公开获取范围。本机可用性另通过 `source_attached` 与实际读回确认。段落引用要记录文档名、版本、语言、范围、实际原件哈希、物理页、印刷页、节/表/图与核对日期。适用标准另记录项目采用版本、补充/勘误、目标市场、项目批准的限值与测试工况。

## 2026-11-19 原件与线上定位核对

| 结果 | 来源与定位 |
| --- | --- |
| 原件同一 | SLLA272D 物理 3/4/6/7 页。IPC-TM-650 2.4.22C 物理 1/3 页。SBOA263A 和 SBOA269B 均为物理 1/2 页。链接见各源记录。 |
| 同版定位核对 | AN4488 Rev 7 物理 37 页、印刷 37/50、§8.3。ADI Basic Linear Design 第 12 章物理 75 页、印刷 12-73，第 10 章物理 15/18 页、印刷 10.13/10.16，第 13 章物理 15 页、印刷 13.13。MT-031 中文 Rev A 物理 7 页、印刷 7/17、图 5。 |
| 版本和编排有差异 | AN2867 本机 Rev 24，物理 12/13 页。ST 滚动链接实际返回 Rev 25（2026-10）。TI 本机 119 页中文汇编物理 4 页对应独立的 ZHCT465 第 1 页、图 1，线上 SLYY237A 另为 162 页英文合集。 [ZHCT465 中文原文](https://www.ti.com.cn/cn/lit/pdf/ZHCT465) · [SLYY237A 英文合集](https://www.ti.com/lit/eb/slyy237a/slyy237a.pdf) |
| 书目和受控标准 | IPC-2221B、IPC-7351B CN、J-STD-033A 从本机原件及发行方修订目录核版本。图灵出版目录和新华书店书目用于教材识别。标准新版本、教材原文语言和不同扫描方式均须单独定页。 |
| 总量 | 26 个本机原件均通过清单 SHA-256 核对，120 个页引用均在对应 PDF 范围内。94 个可直接读原生文字层，余下 26 个来自三本扫描教材，需要结合本机 OCR 与原页图像。此核对覆盖书目身份、定位和访问边界。工程结论仍须按实际项目工况逐条审查。 |

## 工程域的版本与访问边界

以下保留工程体系手册、工程准则研究和工具生态对标在 2026-11-19 记录的边界。[逐项来源登记](../assets/review-knowledge/lifecycle-sources.json) 共收录 177 个来源编号、180 个书目及工程域条目、17 组制造版次记录。`E02-20` 保留手册当次访问记录，`AEC-Q100-REV-J1`、`AEC-Q200-REV-E` 对应独立工程研究取得的正文及主会话复访边界，可用 `knowledge.py sources` 精确查询。新任务锁定对象版本、正式发布与适用版本，再补正文。

| 证据 | 差异和核对范围 |
| --- | --- |
| EMC、绝缘及产品范围 | IEC 61000-4-2:2025 Ed3、IEC 60664-1:2020+AMD1:2025 Ed3.1、IEC 62368-1:2023 Ed4（2025-08 更正）为出版元数据。数值表仍需受控正文，目标市场独立核对 ANSI/UL 版本与国家差异。CISPR 32 的 2026 PRV/FDIS 与 2015+A1:2019 正式合并版分存。旧 ISO 7637-2 Pulse 5 名称仅供追溯，抛负载测试按采用的 ISO 16750-2 与 OEM 工况。 [IEC 61000-4-2](https://webstore.iec.ch/en/publication/68954) · [IEC 60664-1](https://webstore.iec.ch/en/publication/107319) · [IEC 62368-1](https://webstore.iec.ch/en/publication/69308) · [ANSI/UL 62368-1](https://www.shopulstandards.com/ProductDetail.aspx?productId=UL62368-1_4_S_20250731) · [CISPR 32 正式合并版](https://webstore.iec.ch/en/publication/65836) · [CISPR 32 PRV](https://webstore.iec.ch/en/publication/117658) · [ISO 16750-2](https://www.iso.org/standard/76119.html) |
| 安全度量、降额与资格 | ISO 26262-5 与 IEC 61508 的目录、原厂复述和受控条款分开，PMHF `<` 与 `≤` 的出处及处理见[系统安全](../../plan-electronic-product/references/system-safety-and-requirements.md)。MIL-HDBK-1547A 已取消，历史资料不可当现行降额标准。AEC J1/E 有独立正文记录及复访限制，详见[器件资格](component-qualification.md)。GJB 现行受控正文和企业内部评审规范未取得，保持待核。 |
| 器件文档 | ST AN2867 本机 Rev 24、官网下载 Rev 25，分别定页。ES0182 的目录 V19 与实读 Rev18 的差异和硅修订范围见[首次上电](../../hardware-design-review/references/bring-up-troubleshooting.md)。Infineon 线性 SOA 文档页脚 2017 与参考文献 2022 不一致，TI SLVA432 有控制模式措辞冲突，见[电源与模拟审查](../../design-and-review-circuit/references/power-and-analog-review.md)。TI CC2651R3SIPA 的 2026 封装附录与 SWRS278B 正文修订分别记录。 |
| 高速协议 | ISO 11898-2 的 2026 Ed4 已发布，2024 版已撤销，条文须授权读取。USB 2.0 基版、增补/ECN 和 2026-04 Electrical Compliance v1.08 分开，已读测试规范不覆盖全部 ECN。IEEE PoE 的 802.3bt-2018 与项目采用的后续合集分开。MIPI D-PHY 3.6、C-PHY 3.1、PCIe Base 7.1 只核发布元数据，依代际、配套规范及 ECN 补正文。 [ISO 11898-2](https://www.iso.org/standard/90697.html) · [USB-IF 文档目录](https://www.usb.org/documents?search=usb+2.0+specification) · [IEEE 802.3bt](https://www.ieee802.org/3/bt/) · [MIPI D-PHY](https://www.mipi.org/specifications/d-phy) · [MIPI C-PHY](https://www.mipi.org/specifications/c-phy) · [PCIe Base 7.1](https://pcisig.com/specification/pci-express-base-specification-revision-71) |
| 材料与环境 | IEC 60068-2-64:2026 Ed3 官方页面替代 2008+A1:2019，旧搜索摘要不得覆盖。-2-1/-2-2/-2-78 的 2025 版是公开范围，项目严酷度另定。IPC-2152 2009 仅有公开预览与原始试验摘证，缺完整图表。目录的 No Longer Maintained 单列。9704A 公开目录只说明测量方法范围，缺封装允许应变。 [机电专项](../../pcb-layout-review/references/materials-mechanics-and-environment.md) · [IPC-2152 官方预览](https://www.ipc.org/TOC/IPC-2152.pdf) |
| 制造与 DFT | IPC-2223F/4204C 见新发布目录，旧修订表仍显示 2223E。J-STD-046A/048A 的 IPC/ANSI 2026 目录与部分 JEDEC/ECIA 的 2025 发行记录并列，受控合同确认生效版和 PCN/EOL 时限。IPC-7351B、J-STD-033D 的 No Longer Maintained 单存，产品采用关系及适用控制仍要确认。IEEE 1149.1-2013 与在研 P1149.1 分开，BSDL、链路和覆盖需工程证据。 [IPC 修订表](https://www.electronics.org/ipc-document-revision-table) · [IPC 新发布目录](https://www.electronics.org/recently-released-ipc-standards-and-documents) · [IEEE 修订项目](https://standards.ieee.org/ieee/1149.1/10977/) |
| 制造交换文件 | Ucamco Gerber 2026.05 和 ODB++Design 8.1 Update 4 用发布方实际正文。ODB++ 旧 FAQ 的 8.1.2 与实际 8.1U4 保留差异。IPC-2581C 本轮只有目录/范围，板厂能力和 CPL 定义使用实际服务条件，放行留制造包 CAM 回读。 [Ucamco 文件](https://www.ucamco.com/en/gerber/downloads/) · [ODB++Design 8.1U4](https://odbplusplus.com/wp-content/uploads/sites/2/2024/08/odb_spec_user.pdf) · [IPC-2581C 目录](https://www.ipc.org/TOC/IPC-2581C-toc.pdf) |
| 工程专著 | 《The Art of Electronics》英文第 3 版与本机中文分册分开。Wiley 的 Ott 书目结构化第 1 版与同页简介 third edition 不一致，按题名和 ISBN 9780470189306 取 2009 书目。Bogatin 第 3 版的不同日期按 ISBN 9780134513416 纸本 2018 记。Erickson/Maksimović 第 3 版纸本和电子版分别为 2020-08-16、2020-07-14。Montrose 各地区目录月份不同，按 2000 年版记录。出版目录和作者前言只提供学科体系和回读入口。 [作者目录](https://artofelectronics.net/the-book/table-of-contents/) · [Ott](https://www.wiley-vch.de/en/areas-interest/engineering/electrical-electronics-engineering-10ee/noise-in-electronic-systems-10ee42/electromagnetic-compatibility-engineering-978-0-470-18930-6) · [Bogatin](https://www.informit.com/store/signal-and-power-integrity-simplified-9780134513416) · [Erickson/Maksimović](https://link.springer.com/book/10.1007/978-3-030-43881-4) · [Montrose](https://montrosecompliance.com/publications-books/) |
