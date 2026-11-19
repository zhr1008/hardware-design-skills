---
name: schematic-analyzer
description: |
  Use when analyzing KiCad schematics (.kicad_sch) or Cadence OrCAD/Allegro schematics,
  identifying what a component or IC does, tracing nets, buses, signal paths, or power distribution,
  extracting subsystem topology, or reviewing hardware architecture for design review, BSP bring-up,
  or test planning. Trigger on requests about I2C/SPI/UART/USB buses, power trees, signal flow,
  component roles, root schematic selection in hierarchical designs, and Chinese terms such as
  原理图分析, 拓扑提取, 器件角色, 信号流, 电源树.

metadata:
  compatibility: "Requires Python; the KiCad CLI path additionally needs kicad-cli. Use current runtime component/PDF tools when needed; an old MCP name is not a mandatory dependency."
---

# Schematic Analyzer

For reusable or company projects, preserve the root sheet, hierarchy, revision and
source hashes in `hardware-project-library`. Extract observed topology and roles
separately from inferred intent. Keep no-connect markers, literal NC net names,
normally-closed terminals and DNP assembly states distinct. The parser is evidence
extraction, not an electrical approval or permission to execute project code.

The local `rules/component_rules.yaml` supplies conservative navigation hints and
structural ranking defaults. These are heuristic candidates, not manufacturer
identity or specification evidence; project rule overlays and actual datasheets
take precedence. General parser and CLI tests use a generated KiCad hierarchy, or a
temporary copy of the original design when configured. Board-specific regressions
use `SCHEMATIC_ANALYZER_TEST_DATA` (Denali and E1005_v01). Missing original
fixtures and missing native connectivity support are reported explicitly.

Analysis of KiCad schematics, or Cadence OrCAD/Allegro schematics (Allegro netlist pstxnet.dat/pstxprt.dat
combined with OrCAD Capture XML export .xml) via CLI tools.
Produces accurate answers—query what's needed for reliable conclusions, never dumps
raw files, never guesses without grounding.

## 保存态查询

从技能根目录使用 `python scripts/schematic-cli.py --help`。单个位号或网络走 `query`，跨页架构从 `overview` 找根页、核心器件和跨页网络。`cache` 用于缓存管理。运行前按格式确认文件、根页与所需解析后端。

对每条结论保留位号、引脚、网络、层级和版次。器件身份需要额外资料时复用 `component-sourcing`，电气限值用 `ee-datasheet-master` 核原厂 PDF，再回到该引脚对应的网。正式审查记录覆盖和未知项。

[查询命令、示例及排障](references/analyzer-query-guide.md) · [各查询模式和证据要求](SCHEMATIC_STRATEGY.md)
