# EDA release adapters

Use the authoritative EDA's native output job or CLI. Record tool/version,
source revision, origin, units, side/rotation convention, layer mapping, and
every command or job configuration needed to reproduce the release.

- **KiCad:** native Gerber/drill/position/BOM/STEP/PDF exports; pair board and
  project files because rules and stackup may live outside the board.
- **Altium:** controlled OutputJob for Gerber/ODB++/IPC-2581, NC drill, BOM,
  pick-and-place, assembly drawing, and 3D evidence.
- **EasyEDA Standard/Pro:** use the matching edition's fabrication and assembly
  export; verify origins and rotations independently.
- **EAGLE/Fusion:** use CAM processor/manufacturing outputs plus native BOM/CPL;
  preserve the exact CAM configuration.
- **ODB++/IPC-2581:** may replace several loose files when the manufacturer
  accepts them, but still include BOM/assembly and a manifest of the delivered
  package.

For Gerber/Excellon output, a separately installed [Gerbonara CLI](https://gerbolyze.gitlab.io/gerbonara/cli.html)
can read layer metadata and generate an independent local view. Verify the
inferred layer mapping against the export log before using it as evidence.
Run the [BOM/CPL check](assembly-check.md) against the same assembly variant.

If only derived fabrication files exist, audit and package them but mark native
source traceability BLOCKED or USER_REVIEW. Never reconstruct a release revision
from filenames alone.

已有 KiBot 产物可以按实际角色提交给原有清单构建器。保留输出配置、源摘要、版本与变体，以及 Gerber、钻孔、BOM/CPL 的独立读回。DRC 使用同源且现有检查器支持的原生报告。旧文本日志或 preflight 成功提示作为旁证，原理图一致性与规则覆盖另行核实。 [KiBot DRC](https://kibot.readthedocs.io/en/latest/configuration/preflights/drc.html)
