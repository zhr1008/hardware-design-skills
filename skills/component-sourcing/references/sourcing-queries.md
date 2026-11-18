# 采购与检索细则

## 多供应商入口

跨平台采购使用 `component_providers` 检查实现、凭据配置、官方申请渠道和实际请求状态；配置不等于已联通。随后用 `component_search` 检索、`component_get` 确认供应商 SKU/MPN，再用 `component_offers` 按数量报价。统一搜索的 limit 是每个供应商的分页大小；读取 `complete/provider_errors` 和各供应商 `has_more`，条件只在本次取得的分页内过滤。

贸泽和 DigiKey 由用户自行申请官方 API，填写私有文件并通过 `COMPONENT_SUPPLIERS_CONFIG` 指定，或使用环境变量。申请及填写步骤见仓库 `docs/supplier-setup.md`；不要让用户在聊天、Issue 或公共日志提交密钥。华秋当前仅提供官方申请渠道，未验证协议前返回 `UNSUPPORTED_PROVIDER`。

只比较同制造商、MPN、封装、币种和市场的报价组；包装变体的库存不相加，不隐式换汇。检查 MOQ、订购倍数、原始币种、实际订购量和快照时间，运费税费未知。国内采购按下文的国内库存池处理。

## 精确查询和选型

### 标准库优先与外部检索

1. 用户提供标准阻容 JSON 索引时，按 `lcsc_id`（或 `code`）和完整 `mpn` 精确匹配，或用 `group`、`package` 和 `parameters` 筛规格。检查请求中的全部硬条件。查询输出保留原始单位、来源和核对日期。适用用户或项目品牌偏好时，在证据相当的候选中排序。
2. 库内候选满足硬条件、数量和所需证据时，可用同一 C 号下已核对且仍适用的 `comment`、`generic_description`、`description` 和 `url`。涉及电气适用性或替代时按原厂证据判断。按命中的 C 号查询实时库存和数量价，索引中的采购信息仅作留档。需要符号或封装时，用 `symbol`、`footprint` 定位用户提供的对应 `.IntLib`。 [离线检查](altium-assets.md#离线操作-altium-库与已保存工程)
3. 索引未提供、不可读、未覆盖该类器件、候选不足或证据有缺口时，按需要查询立创、原厂及其它渠道。可并行调用立创 MCP 和搜索公开网页。立创 MCP 按准确 C 号、MPN 或规格查询，网络搜索可给料号或规格加 `site:item.szlcsc.com` 找国内商品页，也可定位原厂产品页和 Datasheet。明确要求全市场、跨渠道或网络搜索时，覆盖用户指定的范围。
4. 立创 MCP 超时、限速、失败或漏项时，打开网络搜索找到的实际商品页核对 C 号、MPN、品牌和封装。同一立创建议按准确 C 号合并，保留来源差异。只报告当前可证实的库存与数量价，缺证字段写「待核实」。

公开技能包提供只读查询程序，索引和 `.IntLib` 由用户自行提供。索引采用 UTF-8 JSON 数组，每个器件对象可含 `lcsc_id` 或 `code`、`mpn`、`group`、`package`、`brand`，以及按原字段名保存文本规格的 `parameters` 对象。从技能目录运行以下命令。

```powershell
python -X utf8 scripts/query_passive_index.py path/to/standard-passives.json --code C900000001
python -X utf8 scripts/query_passive_index.py path/to/standard-passives.json --mpn SAMPLE-0603-100NF
python -X utf8 scripts/query_passive_index.py path/to/standard-passives.json --group 贴片电容_0603 --package 0603 --param '容值=0.1uF' --param '额定电压>=50V' --param '温度系数=X7R'
```

重复给出的筛选条件必须同时成立。`--param` 按 `parameters` 中的准确字段名匹配。`=` 支持文本对照及同量纲换算，`>=` 和 `<=` 需要支持的数值单位，例如 `Ω`、`kΩ`、`mΩ`、`F`、`nF`、`uF`、`V`、`W`、`A`、`%`、`ppm/℃`、`mm` 或 `h`。文本规格保留原拼写。按 `unknown_conditions` 补查缺失项、占位值或无法直接比较的条件。`matched_count` 统计库内明确满足所传条件的行，`pending_count` 统计无已知冲突但需补证的行，`--limit` 限制两组各自展示的行数，`truncated` 提示还有结果。工程适用性、库件几何和采购状态另按所需证据核对。

### 精确 C 编号

```text
szlcsc_get_part(identifier="Cxxxxxx", include_procurement=false)
```

需要替代时：

```text
szlcsc_find_alternatives(identifier="Cxxxxxx", in_stock_only=false)
```

用户明确需要现货时再套用库存硬约束。

只比较技术项时复用已有详情，再定向获取缺少的 `szlcsc_get_part(include_procurement=false)`。需同时比较采购字段时可用 `szlcsc_compare_parts`，它会走器件详情的默认采购补全。指定数量价仍用单独的数量报价入口。

最终兼容性仍核 Datasheet。

精确查询不接受唯一模糊结果。MPN 对应多个 C 编号时检查 `AMBIGUOUS_PART`，回到候选的封装/品牌及明确 C 编号，不擅自选第一条。

### 明确 MPN

1. 用 `szlcsc_get_part(identifier=MPN, include_procurement=false)` 核对完整订购号。
2. 遇到 `AMBIGUOUS_PART` 用 `szlcsc_search` 找同型号条目，再按品牌、封装和 C 编号逐项核对。
3. 精确查询未命中时用 `szlcsc_discover` 补查系列和后缀，并标明候选的实际订购型号。

普通搜索必须读取 `search_relevance.hard_pass`，不要盲信商城原始排序。

### 功能/参数选型

通过立创 MCP 外查时，普通中文需求优先调用 `szlcsc_select`。把用户原话传给 `request`，通过 `conditions` 补充明确但未自动识别的条件。保留返回的 `selection`，后续只改精度、封装或数量时将它传给 `previous`，沿用其他条件。明确要求现货时可单独查询最终候选的当前库存，给出数量后查询该数量的报价。

按 [AD 字段规范](ad-field-rules.md) 核实 `pending_evidence` 和最终候选字段。只有达到文件交付终点才走 [固定导出程序](ad-selection-export.md)。

需要扩大系列或封装变体范围时使用下面的入口。

```text
szlcsc_discover(query="AEC-Q100 isolated CAN", family_queries=["ISO1042", "NSI1042"], max_results=10, include_procurement=false)
```

- 先拆分功能、硬条件、偏好及数量；未指定封装/预算/现货时不要自行增加这些硬过滤。
- 默认保留未知库存与价格；多查询、中英文功能词回退、系列扩展和分页由明确预算限制。读取 `coverage.queries / query_errors / remaining_candidates / query_budget_reached`，需要时补充系列词或页数；一次空查询不能声明“没有此器件/市场无货”。
- 覆盖不同后缀、封装与引脚数。例如同一收发器系列可能同时有 8 脚和 16 脚，不因先看到一种就漏掉另一种。
- `exact_identity=false` 是候选或系列变体，不能当作完整请求型号。短系列名精确查询失败后用 discover，不把找到的后缀擅自绑定。
- `requirements.status=unknown`、`constraint_match` 中 missing 是缺证据；`catalog_claim` 仅为商城声明。Q1 后缀不证明 AEC-Q100 资格，仍核对精确订货号的制造商资料。
- 普通 `szlcsc_search` 默认保持数组响应，设置 `include_coverage=true` 返回 `{results,count,coverage}`。每页检查上游 30 条，按 `coverage.next_cursor` 的 page/result_offset 继续以取回页内其余候选；输出 max_results 不等于检索完整度。不要只缩窄一个型号再报告全部候选。

对已发现系列进行电气条件比较：

```text
szlcsc_parametric_search(...)
```

必须检查 `constraint_match.all_matched` 以及每个参数的 `actual / expected / matched`。默认不排除库存未知的候选；明确的商业过滤在当前详情补全后执行。

### 国内库存和按数量报价

采购前优先调用聚焦 Tool：

```text
szlcsc_get_stock(identifier="C2040", refresh=true)
szlcsc_get_pricing(identifier="C2040", quantity=10, refresh=true)
```

- `inventory_pool="SZLCSC_domestic_retail"` 是国内零售库存；读取 stock/total_stock/warehouse_stock、MOQ 和订购倍数。
- 报价读取 `requested_quantity / order_quantity / unit_price_cny / line_total_cny`，不得把高数量阶梯单价套给小批量；实际订购量可能因 MOQ/倍数调整。
- `full_pack_qty` 是整盘/整包装数量，不是 MOQ。仅显式购买下限可用于提高订购量；缺失 MOQ 保持 null。阶梯 `max_qty=null` 可表示末档无上限。
- `refresh=true` 绕过 TTL 缓存。检查 `data_freshness` 与 `warnings`；缓存时间是来源快照时间，不是价格有效期保证。
- 详情 Tool `szlcsc_get_part` 也支持 refresh。缺库存/价保持 null；请求失败不能用旧缓存冒充实时数据。
- `procurement.source=public_product_page` 表示按身份核对了当前商品页，它覆盖冲突的旧移动 API 信息。商品页取不到时不保留旧价/库存冒充当前数据。
- `advertised_unit_price_cny` 是公开展示价，未附数量范围时不能作为 MOQ/指定数量报价；此时 `quantity_price_verified=false`、阶梯为空、按数量单价/总价为 null。需要用户在商品页确认，不绕过签名接口。缓存仅保留当前商品必要字段，TTL 5 分钟。

### JLCPCB 装配库

```text
szlcsc_jlcpcb_search(query="100nF", library_type="basic", package="0603", min_stock=10, page=1, page_size=10)
szlcsc_jlcpcb_categories(refresh=false)
```

- library_type 可用 all/basic/preferred/extended/no_fee；preferred 优先于 expand 分类，no_fee 合并 basic 与 preferred 两个分页窗口并去重，最多返回 2×page_size 条。
- `complete=false` 表示 no_fee 的某个库不可用；必须报告 `unavailable_libraries`，不能把保留的部分结果当成完整查询。
- `inventory_pool="JLCPCB_assembly"` 与国内零售是不同库存池，不能相加或互相代替。
- 装配报价币种未明确时保持 null；不能用国际美元价补齐国内 CNY 报价。
- 分类字典缓存 24 小时。403/429 或未知字段必须报告限制，不绕过验证码、登录、WASM 或指纹限制。

### MCP 错误与调用边界

查询失败先看实际错误与证据范围；需操作活动 AD 文档时，按宿主权限与实际参数核对前台和写入副作用。

失败检查 `isError` 与 `error.code / error.message / error.retryable / error.retry_after_seconds`。PART_NOT_FOUND/AMBIGUOUS_PART/INVALID_ARGUMENT 不盲目重试；RATE_LIMITED 按等待时间处理；ACCESS_DENIED 停止并报告访问条件。批次结果还需检查逐项失败。

关键上限：搜索/候选池 1–50，compare 20、下载 100、Datasheet 同步 200、Altium import batch 50、smoke 5；非空列表不得被静默截断。可读取 `szlcsc://sourcing-guide` 或获取 `select_domestic_component` Prompt 辅助选型。

## 替代料最终核对顺序

1. Datasheet covered MPN。
2. Package / terminal numbering。
3. pinout / pin function。
4. 输入输出与绝对最大额定值。
5. 精度、容差、温漂等性能参数。
6. 稳定性条件与外围要求。
7. thermal / temperature。
8. 国内库存。
9. `small_batch_price_cny`。

## 失败降级

- 准确 C 号经国内来源仍查不到时，报告检索范围并保留待核实。
- MPN 无 exact：不要强绑，转参数化搜索或人工确认候选。
- price/stock 缺失：unknown，不猜 0。
- Datasheet 缺失：不能完成最终 package/pin verification。
- SchLib/PcbLib parse 失败：保留 last-good stale record，报告具体文件。
- footprint link 多候选：ambiguous。
- property conflict：保持 conflict，不自动覆盖。
- `altium-cruncher` 缺失只影响转换/merge，不应假装生成文件。
- migration 有 blocker：停止真实迁移。
