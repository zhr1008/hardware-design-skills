import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


INSTALLER = Path(__file__).resolve().parents[1] / "scripts" / "install_skills.py"


class InstallerTest(unittest.TestCase):
    def setUp(self):
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        root = Path(work.name)
        self.bundle = root / "bundle"
        self.installer = self.bundle / "scripts" / INSTALLER.name
        self.installer.parent.mkdir(parents=True)
        shutil.copyfile(INSTALLER, self.installer)
        self.target = root / "profile" / "skills"
        self.hardware = self.write_skill("hardware", "# Hardware")
        self.specialist = self.write_skill("example-specialist", "# Specialist")

    def write_skill(self, name, text):
        directory = self.bundle / "skills" / name
        directory.mkdir(parents=True)
        (directory / "SKILL.md").write_text(text, encoding="utf-8")
        return directory

    def run_installer(self, *args):
        return subprocess.run(
            [sys.executable, "-X", "utf8", str(self.installer), "--target", str(self.target), *args],
            capture_output=True, encoding="utf-8", check=False, timeout=20,
        )

    def make_symlink(self, link, target, directory=False):
        try:
            link.symlink_to(target, target_is_directory=directory)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"本机不能创建测试符号链接 {error}")

    def test_dry_run_and_install_copy_entire_bundle(self):
        assets = self.specialist / "assets"
        assets.mkdir()
        (assets / "example.csv").write_bytes(b"Value\n0603\n")
        (self.specialist / ".env").write_text("private-bundle-marker", encoding="utf-8")
        (assets / ".metadata").write_text("private-asset-marker", encoding="utf-8")
        cache = self.specialist / "__pycache__"
        cache.mkdir()
        (cache / "example.pyc").write_bytes(b"cache")

        self.assertEqual(self.run_installer("--dry-run").returncode, 0)
        self.assertFalse(self.target.parent.exists())
        self.assertEqual(self.run_installer().returncode, 0)
        self.assertEqual(
            (self.target / self.specialist.name / "assets" / "example.csv").read_bytes(),
            b"Value\n0603\n",
        )
        self.assertTrue((self.target / "hardware" / "SKILL.md").is_file())
        self.assertFalse((self.target / self.specialist.name / ".env").exists())
        self.assertFalse((self.target / self.specialist.name / "assets" / ".metadata").exists())
        self.assertFalse((self.target / self.specialist.name / "__pycache__").exists())

    def test_identical_skill_is_skipped_and_local_hidden_data_stays(self):
        self.assertEqual(self.run_installer().returncode, 0)
        file = self.target / "hardware" / "SKILL.md"
        before = file.stat().st_mtime_ns
        private = file.parent / ".codex-install-source.json"
        private.write_text("local marker", encoding="utf-8")
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("相同且跳过 2 项", result.stdout)
        self.assertEqual(file.stat().st_mtime_ns, before)
        self.assertEqual(private.read_text(encoding="utf-8"), "local marker")

    def test_conflicting_skill_blocks_the_whole_bundle(self):
        installed = self.target / "hardware"
        installed.mkdir(parents=True)
        original = installed / "SKILL.md"
        original.write_text("# Existing skill", encoding="utf-8")
        for flags in [("--dry-run",), ()]:
            result = self.run_installer(*flags)
            self.assertEqual(result.returncode, 1)
            self.assertIn("hardware", result.stderr)
            self.assertFalse((self.target / self.specialist.name).exists())
            self.assertEqual(original.read_text(encoding="utf-8"), "# Existing skill")

    def test_source_symlink_blocks_without_reading_target_file(self):
        outside = self.bundle.parent / "outside.txt"
        outside.write_text("outside marker", encoding="utf-8")
        self.make_symlink(self.hardware / "linked.txt", outside)
        self.assertEqual(self.run_installer().returncode, 1)
        self.assertFalse(self.target.exists())

    def test_target_ancestor_symlink_blocks_install(self):
        outside = self.bundle.parent / "outside"
        outside.mkdir()
        self.make_symlink(self.target.parent, outside, directory=True)
        self.assertEqual(self.run_installer().returncode, 1)
        self.assertEqual(list(outside.iterdir()), [])

    def test_existing_skill_symlink_blocks_install(self):
        self.target.mkdir(parents=True)
        self.make_symlink(self.target / self.hardware.name, self.hardware, directory=True)
        result = self.run_installer()
        self.assertEqual(result.returncode, 1)
        self.assertIn("hardware", result.stderr)
        self.assertFalse((self.target / self.specialist.name).exists())

    def test_invalid_skill_directory_blocks_before_target_creation(self):
        (self.specialist / "SKILL.md").unlink()
        self.assertEqual(self.run_installer().returncode, 1)
        self.assertFalse(self.target.exists())

    def test_changed_source_rolls_back_only_the_new_installation(self):
        self.target.mkdir(parents=True)
        existing = self.target / "unrelated"
        existing.mkdir()
        marker = existing / "SKILL.md"
        marker.write_text("# Existing", encoding="utf-8")
        source = self.bundle / "skills"
        functions = runpy.run_path(str(self.installer))
        pending, _ = functions["plan_installation"](source, self.target)
        (self.hardware / "SKILL.md").write_text("# Changed", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "安装期间源文件内容改变"):
            functions["install"](source, self.target, pending)
        self.assertEqual(list(self.target.iterdir()), [existing])
        self.assertEqual(marker.read_text(encoding="utf-8"), "# Existing")


if __name__ == "__main__":
    unittest.main()
