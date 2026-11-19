import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SKILL = Path(__file__).resolve().parents[1] / "skills/hardware"
SCRIPT = SKILL / "scripts/knowledge.py"


class EngineeringKnowledgeTest(unittest.TestCase):
    def test_unified_bibliography_preserves_version_conflicts_and_catalog_access(self):
        records = self.query("sources", "AN2867")["results"]
        self.assertEqual({item["catalog"] for item in records}, {"rule_source", "handbook"})
        local = next(item["record"] for item in records if item["catalog"] == "rule_source")
        self.assertIn("24", local["edition"])
        self.assertEqual(local["source_url_status"], "version_conflict")
        exact = self.query("sources", "B01", "--limit", "1")["results"][0]
        self.assertEqual(exact["id"], "B01")
        self.assertFalse(exact["record"]["full_text_reviewed"])
        for identity, edition in (("AEC-Q100-REV-J1", "2026-03-24"), ("AEC-Q200-REV-E", "2023-03-20")):
            entry = self.query("sources", identity, "--limit", "1")["results"][0]
            self.assertEqual(entry["id"], identity)
            original = entry["record"]["occurrences"][0]
            self.assertIn(edition, original["edition_and_identity"])
            self.assertIn("复访受限", original["recorded_access_and_limits"])

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.data = self.root / "assets/engineering-library"
        self.data.mkdir(parents=True)
        self.manifest = self.data / "manifest.json"
        self.references = self.root / "references/library"
        self.references.mkdir(parents=True)
        self.docs = [
            {"id": "A1", "title": "示例 ABC", "edition": "B",
             "reference_file": "references/library/a.md", "source_sha256": "a" * 64},
            {"id": "A2", "title": "另一个文档", "edition": "C",
             "reference_file": "references/library/b.md", "source_sha256": "b" * 64},
        ]
        self.write_json(self.manifest, {"schema_version": 1, "documents": self.docs})
        (self.references / "a.md").write_text(
            "# A\n\n## PDF page 16\n\nＡＤＣ－１采样，return current。\n\n## 源阻抗\n\n只含时间常数。\n",
            encoding="utf-8",
        )
        (self.references / "b.md").write_text(
            "## PDF page 16\n\nADC-1 return current，第二份文件。\n", encoding="utf-8",
        )

    def write_json(self, path, payload):
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def query(self, *args, private=False, expected=0):
        prefix = ["--library", str(self.root)] if private else []
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-B", str(SCRIPT), *prefix, *args],
            text=True, capture_output=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.returncode, expected, (result.stdout, result.stderr))
        return json.loads(result.stdout)

    def test_shipped_rules_have_source_metadata_and_filter_without_index(self):
        status = self.query("status")
        self.assertEqual(status["review_rules"], 96)
        self.assertEqual(len(status["rule_domains"]), 9)
        self.assertEqual(status["reference_sources"], 26)
        rule, = self.query("rules", "--id", "pcb-return-path")["rules"]
        self.assertEqual(rule["domain"], "PCB与EMC")
        citation, = rule["evidence"]
        self.assertEqual((citation["pdf_page"], citation["printed_page"]), (75, "12-73"))
        self.assertIn("PCB设计", citation["source"]["display_title"])
        self.assertNotIn("text", citation)

    def test_build_search_by_file_read_and_check_printed_page_version(self):
        self.assertEqual(self.query("build-index", private=True)["indexed_sections"], 3)
        self.assertEqual(self.query("status", private=True)["missing_from_index"], [])
        self.assertEqual(self.query("find", "abc", private=True)["documents"][0]["id"], "A1")
        hits = self.query("search", "--doc", "A1", "adc-1", "return current", private=True)["results"]
        self.assertEqual([(item["document_id"], item["pdf_page"]) for item in hits], [("A1", 16)])
        labels = {"schema_version": 1, "documents": {
            "A1": {"source_sha256": "a" * 64, "pages": {"16": "iv"}},
        }}
        self.write_json(self.data / "page-labels.json", labels)
        page = self.query("read", "A1", "16", "--limit", "5", private=True)
        self.assertEqual((page["text"], page["printed_page"], page["next_offset"]), ("ＡＤＣ－１", "iv", 5))
        labels["documents"]["A1"]["source_sha256"] = "b" * 64
        self.write_json(self.data / "page-labels.json", labels)
        self.assertIn("版本", self.query("read", "A1", "16", private=True, expected=1)["error"])

    def test_missing_escaped_or_existing_index_does_not_silently_pass(self):
        self.assertIn("--library", self.query("search", "adc", expected=1)["error"])
        self.assertIn("index.db", self.query("search", "adc", private=True, expected=1)["error"])
        self.query("build-index", private=True)
        before = (self.root / "scripts/index.db").read_bytes()
        self.assertIn("已存在", self.query("build-index", private=True, expected=1)["error"])
        self.docs[0]["reference_file"] = "../outside.md"
        self.write_json(self.manifest, {"schema_version": 1, "documents": self.docs})
        self.assertIn("相对", self.query("build-index", "--replace", private=True, expected=1)["error"])
        self.assertEqual((self.root / "scripts/index.db").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
