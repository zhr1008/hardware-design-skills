# 本地逐页 OCR 检索

从仓库根目录运行。`--library` 指向仓库外的本地索引目录，目录由使用者用有权处理的文件建立。查询用 Python 标准库读取索引和逐页文字。

```powershell
python -X utf8 skills/hardware/scripts/ocr_books.py --library ../my-ocr-index status
python -X utf8 skills/hardware/scripts/ocr_books.py --library ../my-ocr-index search --book SAMPLE_MANUAL "采样" "数据速率"
python -X utf8 skills/hardware/scripts/ocr_books.py --library ../my-ocr-index read SAMPLE_MANUAL 16
```

`status` 报告总物理页、记录页和有文字的页数。`partial` 表示只覆盖了部分页，`payload_missing` 表示对应的逐页文件缺失。`search` 返回同页命中和短摘要。`read` 按从 1 开始的 PDF 物理页返回 OCR 文字和已记录的印刷页标。即使所有页都有记录，空页或未成功识别的页也可能没有文字。

## 建立索引

用本机的 OCR 工具生成实际标记为 OCR 的 MinerU 4.x Middle JSON。确定原件 SHA-256、版次和 PDF 物理页数，然后指定本地输出目录。可以在同一次传入按窗口产生的多份 JSON，各物理页只出现一次，支持后续在相同原件和 OCR 配置下补页。使用 `--page-labels` 时提供以物理页号为键、印刷页标字符串为值的 JSON，例如 `{"16":"1"}`。

```powershell
$sourceHash = (Get-FileHash -LiteralPath ../materials/manual.pdf -Algorithm SHA256).Hash.ToLowerInvariant()
python -X utf8 skills/hardware/scripts/pack_mineru_book.py --output ../my-ocr-index --id SAMPLE_MANUAL --title "示例手册" --edition "第 1 版" --source-sha256 $sourceHash --pdf-pages 30 ../materials/middle.json
```

此命令写入 `manifest.json` 与 `<id>.jsonl.gz`。已有的本机 v1 索引也可通过目录路径直接读取。`manifest.json` 的 `schema_version` 为 1，`books` 内记录 `id`、`title`、`edition`、`source_sha256`、`pdf_pages`、`pages_file` 和 `ocr_engine`。压缩文件每行保存一个对象，内含 `pdf_page`、`printed_page` 和 `text`。无法确认的印刷页设为 `null`。

在本地数据目录保管原件、OCR 全文和索引。引用时按相同版次回查公式、表格、单位和页码。
