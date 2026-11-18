from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts import check_publication as publication


class PublicationTreeTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.repo = Path(folder.name)
        publication.git(self.repo, "init", "-q")

    def commit(self, message):
        publication.git(self.repo, "add", "--", "note.txt")
        publication.git(self.repo, "-c", "user.name=Bundle CI", "-c", "user.email=ci@example.com",
                        "-c", "commit.gpgsign=false", "commit", "-qm", message)
        return publication.git(self.repo, "rev-parse", "HEAD").decode().strip()

    def test_private_filename_is_rejected_without_echoing_its_value(self):
        filename = "ghp_" + "Q" * 36 + ".txt"
        (self.repo / filename).write_text("ordinary file contents", encoding="utf-8")
        publication.git(self.repo, "add", "--", filename)
        self.assertEqual(publication.scan(self.repo, staged=True, tree=None), (0, [
            {"path": "[redacted filename]", "line": 0, "rule": "filename-github-token"},
        ]))

    def test_scan_ignores_replace_refs_for_the_published_commit(self):
        content = self.repo / "note.txt"
        content.write_text("publishable\n", encoding="utf-8")
        clean = self.commit("clean")
        content.write_text("local endpoint: " + ".".join(("10", "1", "2", "3")), encoding="utf-8")
        original = self.commit("original")
        publication.git(self.repo, "replace", original, clean)
        substituted = subprocess.check_output(
            ["git", "-C", str(self.repo), "show", "HEAD:note.txt"], encoding="utf-8",
        )
        self.assertEqual(substituted, "publishable\n")

        result = subprocess.run(
            [sys.executable, "-X", "utf8", publication.__file__, "--repo", str(self.repo), "--tree", "HEAD"],
            capture_output=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("private-network-address", result.stdout)

    def test_local_library_json_stays_out_of_public_tree(self):
        paths = [
            "skills/hardware/assets/engineering-library/manifest.json",
            "skills/hardware/assets/ocr-books/manifest.json",
            "skills/hardware/references/library/example/fulltext.md",
            "skills/component-sourcing/assets/standard-passives/index.json",
        ]
        for relative in paths:
            file = self.repo / relative
            file.parent.mkdir(parents=True)
            file.write_text("{}", encoding="utf-8")
        publication.git(self.repo, "add", "--", *paths)
        self.assertEqual(publication.scan(self.repo, staged=True, tree=None), (0, [
            {"path": "[redacted filename]", "line": 0, "rule": "private-directory"},
            {"path": "[redacted filename]", "line": 0, "rule": "private-directory"},
            {"path": "[redacted filename]", "line": 0, "rule": "private-directory"},
            {"path": "[redacted filename]", "line": 0, "rule": "raw-source-corpus"},
        ]))


if __name__ == "__main__":
    unittest.main()
