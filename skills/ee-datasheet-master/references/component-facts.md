# 器件事实核对

用[器件事实 v1](../assets/component-facts.schema.json)记录逐项查证结果。身份固定原厂、完整可订购 MPN 和封装。原厂 PDF 记录版次、来源 URL、SHA-256 和适用身份。逐项写 PDF 阅读器从 1 开始的实际页码以及表、行或图的位置。

- `pin` 保存脚号、名称和角色。NC 和 EP 各有独立角色。
- `absolute_maximum`、`recommended_operating` 和 `electrical_characteristic` 分开。参数记录单位与 `min`、`typ`、`max`，来源未给出的栏填 `null`。只给典型值的资料不能用来填写保证限值。
- `conditions` 记录温度、供电、负载或其他原文工况。空数组表示已核对且本项无额外工况。工况或证据未知时使用 `status: unknown`、`value: null` 并说明原因。

```powershell
python -X utf8 -B scripts/validate_component_facts.py facts.json --pdf original.pdf --expected-mpn EXACT-ORDER-CODE --expected-package QFN-16
python -X utf8 -B scripts/validate_component_facts.py facts.json --pdf original.pdf --verify-pages --expected-mpn EXACT-ORDER-CODE
```

退出码 0 表示结构和已提供的核对项成立，1 表示仍有待核实事实，2 表示输入、摘要或页码不符，或证据后端不可用。传入 `--pdf` 时核对本机字节摘要。正式审查有本地原件时可加 `--verify-pages`，用已配置的 PyMuPDF 核对定位页码是否落在同一份原件的实际页数内。页内表达、原厂归属、适用料号和实际工况的技术判断依赖原页复核。跨页表格或封装图特别需要同时核表头、脚注和适用身份。
