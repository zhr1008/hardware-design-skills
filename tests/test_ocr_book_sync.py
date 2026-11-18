import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "skills/hardware/scripts"


class OcrBookSyncTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.library = self.root / "ocr-index"

    def json_file(self, name, data):
        path = self.root / name
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    def middle(self, name, pages):
        return self.json_file(name, {
            "schema": "docvortex.middle",
            "metadata": {"producer": {"version": "4.0.0"}},
            "extensions": {"mineru": {"tier": "flash", "parse_mode": "ocr"}},
            "pages": [
                {"page_idx": page - 1, "blocks": [
                    {"type": "header", "text": "无关页眉"},
                    {"type": "text", "lines": [{"spans": [{"content": text}]}]},
                    {"type": "image_body", "text": "data:image/png;base64,placeholder"},
                ]}
                for page, text in pages
            ],
        })

    def invoke(self, script, *args):
        return subprocess.run(
            [sys.executable, "-X", "utf8", "-B", str(SCRIPTS / script), *map(str, args)],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )

    def pack(self, *inputs, digest="f" * 64):
        return self.invoke(
            "pack_mineru_book.py", "--output", self.library, "--id", "MANUAL", "--title", "示例手册",
            "--edition", "rev B", "--source-sha256", digest, "--pdf-pages", "3", *inputs,
        )

    def lookup(self, *args):
        result = self.invoke("ocr_books.py", "--library", self.library, *args)
        return result.returncode, json.loads(result.stdout)

    def test_pack_merge_search_and_read_preserve_pdf_and_printed_page(self):
        labels = self.json_file("labels.json", {"2": "iv"})
        first = self.middle("first.json", [(2, "ＡＤＣ 采样数据速率")])
        result = self.pack("--page-labels", labels, first)
        self.assertEqual(result.returncode, 0, result.stderr)
        code, catalog = self.lookup("status")
        self.assertEqual(code, 0)
        self.assertEqual(catalog["books"][0]["coverage"]["status"], "partial")
        second = self.middle("second.json", [(1, "其他内容"), (2, "ＡＤＣ 采样数据速率 1000 SPS"), (3, "")])
        result = self.pack(second)
        self.assertEqual(result.returncode, 0, result.stderr)
        code, report = self.lookup("search", "--book", "MANUAL", "adc", "数据速率")
        self.assertEqual(code, 0)
        self.assertEqual(report["coverage"]["pages_with_text"], 2)
        self.assertEqual(report["coverage"]["status"], "complete")
        self.assertEqual([(row["pdf_page"], row["printed_page"]) for row in report["results"]], [(2, "iv")])
        code, report = self.lookup("read", "MANUAL", 2)
        self.assertEqual(code, 0)
        self.assertEqual(report["page"]["text"], "ＡＤＣ 采样数据速率 1000 SPS")

    def test_overlapping_windows_and_wrong_source_do_not_replace_index(self):
        first = self.middle("first.json", [(2, "旧词")])
        second = self.middle("second.json", [(2, "新词")])
        self.assertEqual(self.pack(first).returncode, 0)
        saved = {path.name: path.read_bytes() for path in self.library.iterdir()}
        self.assertEqual(self.pack(first, second).returncode, 1)
        self.assertEqual(self.pack(second, digest="e" * 64).returncode, 1)
        self.assertEqual({path.name: path.read_bytes() for path in self.library.iterdir()}, saved)

    def test_missing_and_wrong_catalog_cannot_return_matching_results(self):
        self.assertEqual(self.lookup("status"), (1, {"manifest_present": False, "books": []}))
        self.library.mkdir()
        (self.library / "manifest.json").write_text(json.dumps({
            "schema_version": 1, "books": [{"id": "../outside", "pages_file": "../outside.jsonl.gz"}],
        }), encoding="utf-8")
        code, report = self.lookup("search", "--book", "../outside", "关键词")
        self.assertEqual(code, 1)
        self.assertIn("error", report)
        self.assertNotIn("results", report)


if __name__ == "__main__":
    unittest.main()
