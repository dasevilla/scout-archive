import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "src/scripts/generate-merit-badges-change-report.py"
)
COMMIT_SCRIPT = SCRIPT.with_name("commit-changes.sh")


class MeritBadgesChangeReportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / "build/merit-badges"
        self.output.mkdir(parents=True)
        self.deleted = self.write_badge(
            "military-service-veterans", "Military Service & Veterans"
        )
        self.write_badge("swimming", "Swimming")
        self.git("init", "--quiet")
        self.git("add", "build")
        self.git(
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.org",
            "commit",
            "--no-gpg-sign",
            "--quiet",
            "-m",
            "Baseline",
        )

    def git(self, *args):
        return subprocess.run(
            ["git", *args], cwd=self.root, capture_output=True, text=True, check=True
        )

    def write_badge(self, slug, name, **extra):
        path = self.output / f"{slug}-merit-badge.json"
        path.write_text(
            json.dumps({"name": name, "requirements": [], **extra}), encoding="utf-8"
        )
        return path

    def report(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(result.stderr, "")
        self.assertNotIn("Error", result.stdout)
        self.assertNotIn("military-service-veterans-merit-badge.json", result.stdout)
        return result.stdout

    def test_deleted_badge_is_named_from_git_and_not_compared_as_modified(self):
        self.deleted.unlink()
        report = self.report()
        self.assertIn("Archived 1 merit badges", report)
        self.assertIn("Removed badges (1):\n- Military Service & Veterans", report)
        self.assertNotIn("Updated requirements", report)
        self.assertNotIn("No changes detected", report)

    def test_staged_deletion_is_also_reported(self):
        self.deleted.unlink()
        self.git("add", "-u")
        report = self.report()
        self.assertIn("Removed badges (1):\n- Military Service & Veterans", report)
        self.assertNotIn("Updated requirements", report)

    def test_added_modified_and_deleted_badges_are_separate(self):
        self.deleted.unlink()
        self.write_badge("swimming", "Swimming", overview="Updated overview")
        self.write_badge("camping", "Camping")
        report = self.report()
        self.assertIn("New badges (1):\n- Camping", report)
        self.assertIn("Updated requirements (1):\n- Swimming", report)
        self.assertIn("Removed badges (1):\n- Military Service & Veterans", report)

    def test_archive_commit_includes_deleted_badge(self):
        image = self.output / "images/swimming.jpg"
        image.parent.mkdir()
        image.write_bytes(b"test image")
        cubs = self.root / "build/cub-scout-adventures"
        (cubs / "wolf/images").mkdir(parents=True)
        (cubs / "wolf/adventure.json").write_text("{}")
        (cubs / "wolf/images/adventure.jpg").write_bytes(b"test image")
        (cubs / "index.md").write_text("Adventure index")
        self.deleted.unlink()
        self.git("config", "--local", "commit.gpgsign", "false")
        output = self.root / "workflow-output.txt"
        subprocess.run(
            ["bash", str(COMMIT_SCRIPT), str(output), "test-release", self.report()],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=True,
        )
        remaining = self.git(
            "ls-tree",
            "--name-only",
            "HEAD",
            "--",
            "build/merit-badges/military-service-veterans-merit-badge.json",
        )
        self.assertEqual(remaining.stdout, "")
        self.assertIn("has-changes=true", output.read_text())


if __name__ == "__main__":
    unittest.main()
