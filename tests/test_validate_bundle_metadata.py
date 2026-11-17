from pathlib import Path
import tempfile
import unittest

from scripts.validate_bundle import check_skill


class MetadataTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.skill = Path(folder.name) / "sample-skill"
        self.skill.mkdir()
        self.entry = self.skill / "SKILL.md"

    def check_frontmatter(self, description):
        self.entry.write_text(
            f"---\nname: sample-skill\n{description}\n---\n# Instructions\n",
            encoding="utf-8",
        )
        return list(check_skill(self.skill))

    def test_discovery_accepts_colons_and_dashes_in_folded_description(self):
        self.assertEqual(self.check_frontmatter("description: >-\n  说明: use A --- B\n  to review C."), [])

    def test_invalid_yaml_and_duplicate_name_are_rejected(self):
        for metadata in ("description: invalid: extra", "name: sample-skill\ndescription: valid"):
            with self.subTest(metadata=metadata):
                self.assertIn("invalid SKILL.md YAML", self.check_frontmatter(metadata)[0])

    def test_description_must_be_nonempty_text(self):
        for value in ("true", "[]", "'   '", ">", "'[TODO: complete later]'"):
            with self.subTest(value=value):
                self.assertIn("description must be", self.check_frontmatter(f"description: {value}")[0])

    def test_expected_name_and_exact_delimiter(self):
        self.entry.write_text("---\nname: wrong-name\ndescription: text\n---\n", encoding="utf-8")
        self.assertIn("name must match", list(check_skill(self.skill))[0])
        self.entry.write_text("---\nname: sample-skill\ndescription: text\n--- body\n", encoding="utf-8")
        self.assertIn("line-delimited markers", list(check_skill(self.skill))[0])

    def test_explicit_invocation_policy_requires_a_boolean(self):
        agents = self.skill / "agents"
        agents.mkdir()
        config = agents / "openai.yaml"
        config.write_text("policy:\n  allow_implicit_invocation: false\n", encoding="utf-8")
        self.assertEqual(self.check_frontmatter("description: valid"), [])
        config.write_text('policy:\n  allow_implicit_invocation: "false"\n', encoding="utf-8")
        self.assertIn("allow_implicit_invocation must be a YAML boolean",
                      self.check_frontmatter("description: valid")[0])


if __name__ == "__main__":
    unittest.main()
