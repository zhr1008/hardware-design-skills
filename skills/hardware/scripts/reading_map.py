"""Select engineering reading routes and render their navigable overview."""

import argparse
from collections import Counter
import json
from pathlib import Path
from urllib.parse import quote

import chapter_catalogue
from engineering_decision import matches


SKILL = Path(__file__).resolve().parents[1]
MAP_PATH = SKILL / "assets" / "knowledge-map.json"
MANIFEST = Path("assets/engineering-library/manifest.json")


def load_map():
    data = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    if data["schema_version"] != 1:
        raise ValueError("不支持该工程知识地图版本")
    return data


def documents(root):
    manifest = root / MANIFEST
    if not manifest.is_file():
        return {}
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if data["schema_version"] != 1:
        raise ValueError("不支持该工程资料清单版本")
    return {item["id"]: item for item in data["documents"]}


def expand(data, theme_ids, docs, include_further=False, root=None):
    themes = []
    for theme_id in theme_ids:
        theme = data["themes"][theme_id]
        steps = []
        sources = [(role, *detail) for role, detail in theme["sources"].items()]
        if include_further:
            sources.extend(theme.get("further_reading", ()))
        for role, doc_id, locator, question in sources:
            doc = docs.get(doc_id, {})
            chapter = (chapter_catalogue.locate(root or SKILL, doc, locator)
                       if doc and isinstance(locator, int) else None)
            steps.append({
                "role_id": role,
                "role": data["roles"][role],
                "document_id": doc_id,
                "title": doc.get("display_title", doc.get("title", data.get("bibliography", {}).get(doc_id))),
                "edition": doc.get("edition"),
                "question": question,
                "status": "catalogued" if doc else "source_not_in_catalogue",
                **({"chapter": chapter} if chapter else {}),
                **({"pdf_page": locator} if isinstance(locator, int) else {"search_terms": locator}),
            })
        themes.append({**{key: val for key, val in theme.items()
                           if key not in ("sources", "further_reading", "intent_keywords")},
                       "id": theme_id, "reading_steps": steps})
    return themes


def select(mode, topics, prototypes, root=None, intent="", required_themes=(), *, compact=False):
    data = load_map()
    primary = [theme for topic in topics for theme in data["by_topic"].get(topic, ())]
    primary.extend(theme for proto in prototypes for theme in data["by_prototype"].get(proto, ()))
    primary.extend(required_themes)
    inferred = [key for key, theme in data["themes"].items()
                if any(matches(intent, keyword) for keyword in theme.get("intent_keywords", ()))]
    primary.extend(inferred)
    mode_themes = data["by_mode"][mode]
    # The task theme takes precedence. Closure and change modes also need their own evidence.
    ordered = (mode_themes + primary if not primary or mode in ("eco", "verify", "bringup", "release")
               else primary)
    docs = documents(root or SKILL)
    if compact:
        return {
            "catalogue_status": "available" if docs else "not_configured",
            "themes": [{"id": theme, "reference": data["themes"][theme]["reference"]}
                       for theme in dict.fromkeys(ordered)],
        }
    return {"schema_version": 1, "catalogue_status": "available" if docs else "not_configured",
            "inferred_from_intent": inferred, "themes": expand(data, dict.fromkeys(ordered), docs, root=root)}


def render(data, docs, root=None):
    lines = [
        "# 硬件工程知识地图", "",
        "按任务和硬件原型选择主题，再沿三层资料查原文。主题间的连线表示必须结合工程风险复核的交接，具体读取范围由任务限定。",
        "标准、原厂数据手册、项目工况和验收限值单独确认。教材、应用例和实测案例提供模型、候选方法和取证思路。", "",
        "```mermaid", "flowchart LR",
        '    Task["工程任务与硬件原型"] --> Topic["命中的专题"]',
        '    Topic --> Theory["基础理论<br/>模型与关键变量"]',
        '    Theory --> Design["设计参考<br/>拓扑与计算边界"]',
        '    Design --> Practice["工程经验与实测<br/>反例与验证方法"]',
        '    Topic --> Authority["实际器件、项目标准与限值"]',
        '    Practice --> Evidence["本任务验算、仿真或实测证据"]',
        '    Authority --> Evidence',
        '    Evidence --> Adjacent["受影响的相邻专题与专项交接"]',
        "```", "",
        "## 如何使用", "",
        "- `design_flow.py start <mode> --prototype <原型>` 展开任务所需阅读链。日常单项查料、单点计算仍直接执行。",
        "- `reading_map.py show 主题编号` 查看单条阅读链，`reading_map.py list` 列出主题。",
        "- PDF 定位用 `knowledge.py read 文档编号 物理页`，需要看原图时用 `render-page`，按词定位用 `search --doc 文档编号 关键词`。",
        "- 先读能区分备选方案或改变判定的资料。记录实际使用的版次、物理页、原图和相应检查。若未命中、仅有 OCR 导读或欠缺受控标准条文，记录缺证并转定向检索或验证。",
        "- 工程案例记录的是特定设计的条件和结果。使用示例中的数值前核材料、器件、工况、测量口径及版次。", "",
        "[11 域及专项交接](lifecycle-domain-index.md) · [工程资料检索](engineering-knowledge.md)", "",
        "## 专题与相邻问题", "",
        "| 专题 | 对应工程域 | 相邻专题 | 工程产物 |", "| --- | --- | --- | --- |",
    ]
    for key, theme in data["themes"].items():
        related = "、".join(f"[{data['themes'][other]['title']}](#{other})" for other in theme["related"])
        domain_text = "、".join(str(n) for n in theme["domains"])
        lines.append(f"| [{theme['title']}](#{key}) | {domain_text} | {related} | {theme['deliverable']} |")
    for theme in expand(data, data["themes"], docs, include_further=True, root=root):
        ref = theme["reference"]
        link = ref.removeprefix("references/") if ref.startswith("references/") else "../" + ref
        lines.extend(["", f"### {theme['id']}", "", f"**{theme['title']}**。 [专项工作方法]({link})", ""])
        for step in theme["reading_steps"]:
            name = step["title"] or step["document_id"]
            if "pdf_page" in step:
                locator = f"PDF {step['pdf_page']}"
            else:
                locator = "搜索 " + "、".join(step["search_terms"])
            if "chapter" in step:
                locator = step["chapter"]["title"] + " · " + locator
            line = f"- **{step['role']}**。{name} · `{step['document_id']}` · {locator}。{step['question']}"
            item = docs.get(step["document_id"])
            if item:
                path = "../" + quote(item["reference_file"], safe="/")
                anchor = f"#pdf-page-{step['pdf_page']}" if "pdf_page" in step else ""
                line += f" [定位正文]({path}{anchor})"
                if item.get("source_file"):
                    pdf = f"#page={step['pdf_page']}" if "pdf_page" in step else ""
                    line += f" [原件]({quote('../' + item['source_file'], safe='/')}{pdf})"
            lines.append(line)
    if docs:
        if chapter_catalogue.load(root or SKILL):
            lines.extend(["", "[已补 OCR 资料的逐章导航](ocr-chapters.md)", ""])
        counts = Counter(doc.get("knowledge_role") for doc in docs.values())
        lines.extend(["", "## 逐份资料的主要用途", "",
                      "主要用途便于浏览。同一份书可在不同专题承担不同角色。按原件版次和来源状态判断效力。", ""])
        for role, label in data["roles"].items():
            lines.extend([f"### {label}（{counts[role]} 份）", ""])
            for doc in sorted(docs.values(), key=lambda row: row.get("display_title", row["title"])):
                if doc.get("knowledge_role") != role:
                    continue
                path = quote("../" + doc["reference_file"], safe="/")
                coverage = (f"文字 {doc['units_with_text']}/{doc['units']} 页或段"
                            if "units_with_text" in doc and "units" in doc else "正文覆盖未登记")
                source_status = doc.get("source_status", "来源状态未登记")
                title = doc.get("display_title", doc["title"])
                lines.append(f"- [{title}]({path}) · `{doc['id']}` · {coverage} · {source_status}。")
            lines.append("")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, default=SKILL)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    show = sub.add_parser("show")
    data = load_map()
    show.add_argument("theme", nargs="+", choices=data["themes"])
    output = sub.add_parser("render")
    output.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    docs = documents(args.library)
    if args.command == "render":
        args.output.write_text(render(data, docs, args.library), encoding="utf-8")
        return
    result = ({id: theme["title"] for id, theme in data["themes"].items()}
              if args.command == "list" else expand(data, args.theme, docs, include_further=True, root=args.library))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
