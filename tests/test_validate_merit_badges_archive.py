import importlib.util
import json
import tempfile
import unittest
from copy import deepcopy
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
        "scoped_clauses": [],
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
    def test_duplicate_sibling_warning_preserves_content(self) -> None:
        first = requirement("a")
        first["text"] = "Explain the career. Resources: Career video"
        second = requirement("b")
        second["text"] = "Explain\n the career."
        second["resources"] = [{"title": "Hobby video", "url": "https://example.org"}]
        requirements = [first, second]
        original = deepcopy(requirements)
        warnings: list[str] = []

        validate_merit_badges_archive._validate_duplicate_sibling_text(
            requirements, "requirements", warnings
        )

        self.assertEqual(requirements, original)
        self.assertEqual(len(warnings), 1)
        self.assertIn("b duplicates sibling requirement text at a", warnings[0])

    def test_duplicate_check_skips_containers_empty_and_invalid_text(self) -> None:
        container = requirement("a")
        container["sub_requirements"] = [requirement("1")]
        leaf = requirement("b")
        leaf["text"] = container["text"]
        warnings: list[str] = []

        validate_merit_badges_archive._validate_duplicate_sibling_text(
            [container, leaf, {}, {"text": ""}, {"text": None}, None],
            "requirements",
            warnings,
        )

        self.assertEqual(warnings, [])

    def test_distinct_instructions_and_different_parents_do_not_warn(self) -> None:
        first = requirement("1")
        first["sub_requirements"] = [requirement("a")]
        second = requirement("2")
        second["sub_requirements"] = [requirement("a")]
        warnings: list[str] = []

        validate_merit_badges_archive._validate_requirement_tree(
            [first, second], "requirements", [], warnings
        )

        self.assertFalse(any("duplicates sibling" in warning for warning in warnings))

    def test_empty_lab_record_is_still_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "expired-content-merit-badge.json"
            file_path.write_text(
                json.dumps(
                    {
                        "name": "",
                        "url": "https://www.scouting.org/expired-content/",
                        "is_lab": True,
                        "requirements": [],
                    }
                ),
                encoding="utf-8",
            )
            errors, _warnings = validate_merit_badges_archive.validate_badge_content(
                file_path
            )
        self.assertIn("Empty required field: name", errors)
        self.assertTrue(
            any(error.startswith("Only 0 requirements found") for error in errors)
        )
        self.assertTrue(
            any(error.startswith("File size too small") for error in errors)
        )

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

    def test_warns_when_action_clause_scope_is_ambiguous(self) -> None:
        ambiguous = requirement("1")
        ambiguous["text"] = "Explain the rule and do ONE of the following:"
        ambiguous["content"] = [{"type": "text", "value": ambiguous["text"]}]
        ambiguous["scoped_clauses"] = [
            {"text": ambiguous["text"], "scope": "ambiguous"}
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "ambiguous-scope-merit-badge.json"
            file_path.write_text(
                json.dumps(badge([ambiguous, requirement("2")])),
                encoding="utf-8",
            )

            errors, warnings = validate_merit_badges_archive.validate_badge_content(
                file_path
            )

        self.assertFalse(errors)
        self.assertTrue(
            any("ambiguous action scope" in warning for warning in warnings)
        )

    def test_rejects_suppressed_requirement_scoped_action(self) -> None:
        suppressed = requirement("1")
        suppressed["requires_response"] = False
        suppressed["scoped_clauses"] = [
            {"text": suppressed["text"], "scope": "requirement"}
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "suppressed-action-merit-badge.json"
            file_path.write_text(
                json.dumps(badge([suppressed, requirement("2")])),
                encoding="utf-8",
            )

            errors, _warnings = validate_merit_badges_archive.validate_badge_content(
                file_path
            )

        self.assertTrue(
            any("suppresses a requirement-scoped action" in error for error in errors)
        )


if __name__ == "__main__":
    unittest.main()
