import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "scripts"
    / "validate-merit-badges-archive.py"
)
SPEC = importlib.util.spec_from_file_location(
    "validate_merit_badges_archive", SCRIPT_PATH
)
validate_merit_badges_archive = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validate_merit_badges_archive)


def requirement(label: str) -> dict:
    return {
        "id": label,
        "label": label,
        "text": f"Requirement {label}.",
        "requirement_path": label,
        "node_kind": "action_requirement",
        "is_container": False,
        "requires_response": True,
        "content": [{"type": "text", "value": f"Requirement {label}."}],
        "resources": [],
        "sub_requirements": [],
    }


def badge(requirements: list[dict]) -> dict:
    return {
        "name": "Hierarchy Test",
        "overview": "A valid overview long enough for validation.",
        "is_eagle_required": False,
        "is_lab": False,
        "url": "https://www.scouting.org/merit-badges/hierarchy-test/",
        "pdf_url": "",
        "workbook_pdf_url": "",
        "workbook_docx_url": "",
        "shop_url": "",
        "image_url": "",
        "image_filename": "",
        "requirements": requirements,
    }


class ValidateMeritBadgesArchiveTest(unittest.TestCase):
    def test_empty_required_name_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "empty-name-merit-badge.json"
            file_path.write_text(
                json.dumps(
                    {
                        "name": "",
                        "overview": "A valid overview long enough for validation.",
                        "is_eagle_required": False,
                        "is_lab": False,
                        "url": "https://www.scouting.org/merit-badges/empty-name/",
                        "pdf_url": "",
                        "workbook_pdf_url": "",
                        "workbook_docx_url": "",
                        "shop_url": "",
                        "image_url": "",
                        "image_filename": "",
                        "requirements": [requirement("1"), requirement("2")],
                    }
                ),
                encoding="utf-8",
            )

            errors, _warnings = validate_merit_badges_archive.validate_badge_content(
                file_path
            )

        self.assertIn("Empty required field: name", errors)

    def test_warns_about_likely_governed_numbered_siblings(self) -> None:
        governing = requirement("a")
        governing["text"] = "Choose two situations from the list below."
        governing["content"] = [{"type": "text", "value": governing["text"]}]
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "hierarchy-test-merit-badge.json"
            file_path.write_text(
                json.dumps(badge([governing, requirement("1"), requirement("2")])),
                encoding="utf-8",
            )

            _errors, warnings = validate_merit_badges_archive.validate_badge_content(
                file_path
            )

        self.assertTrue(
            any("likely governs numbered siblings" in warning for warning in warnings)
        )

    def test_does_not_warn_for_parenthetical_numeric_references(self) -> None:
        nongoverning = requirement("b")
        nongoverning["text"] = "Compare requirements (1) and (2) above."
        nongoverning["content"] = [{"type": "text", "value": nongoverning["text"]}]
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "hierarchy-test-merit-badge.json"
            file_path.write_text(
                json.dumps(badge([nongoverning, requirement("1"), requirement("2")])),
                encoding="utf-8",
            )

            _errors, warnings = validate_merit_badges_archive.validate_badge_content(
                file_path
            )

        self.assertFalse(
            any("likely governs numbered siblings" in warning for warning in warnings)
        )


if __name__ == "__main__":
    unittest.main()
