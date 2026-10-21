"""Source defects must remain visible without losing distinct official entries."""

import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scout_archive.requirements_pipeline import HtmlExtractor, SemanticProcessor

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "duplicate_content_validator",
    ROOT / "src/scripts/validate-merit-badges-archive.py",
)
validator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validator)
FIXTURES = ROOT / "tests/fixtures/duplicate-content"


def project(requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compare every requirement's wording, source ID, and complete hierarchy."""
    return [
        {key: node[key] for key in ("id", "label", "requirement_path", "text")}
        | {"sub_requirements": project(node["sub_requirements"])}
        for node in requirements
    ]


def flatten(requirements: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {}
    for node in requirements:
        result[node["requirement_path"]] = node
        result.update(flatten(node["sub_requirements"]))
    return result


class DuplicateSourceContentTest(unittest.TestCase):
    def test_live_source_snapshots_preserve_release_text_and_hierarchy(self) -> None:
        for record in json.loads((FIXTURES / "provenance.json").read_text()):
            with self.subTest(badge=record["badge"]):
                raw = HtmlExtractor().extract(
                    (FIXTURES / record["html_fixture"]).read_text()
                )
                requirements = [
                    node.model_dump() for node in SemanticProcessor().process(raw)
                ]
                expected = json.loads(
                    (FIXTURES / record["expected_text_hierarchy"]).read_text()
                )
                self.assertEqual(project(requirements), expected)
                nodes = flatten(requirements)
                first, second = (nodes[path] for path in record["paths"])
                self.assertNotEqual(first["id"], second["id"])
                # Independently inspect the original DOM: the duplication must
                # predate both HTML extraction and semantic normalization.
                soup = BeautifulSoup(
                    (FIXTURES / record["html_fixture"]).read_text(), "html.parser"
                )
                source_instructions = []
                for node in (first, second):
                    elements = soup.select(f".mb-requirement-id-{node['id']}")
                    self.assertEqual(len(elements), 1)
                    text = elements[0].get_text(" ", strip=True)
                    text = re.sub(r"^\([a-z]\)\s*", "", text)
                    text = re.split(r"\bResources?\s*:", text, maxsplit=1)[0]
                    source_instructions.append(" ".join(text.split()))
                self.assertEqual(source_instructions[0], source_instructions[1])
                self.assertEqual(first["label"], record["paths"][0].split(".")[-1])
                self.assertEqual(second["label"], record["paths"][1].split(".")[-1])
                errors: list[str] = []
                warnings: list[str] = []
                validator._validate_requirement_tree(
                    requirements, "requirements", errors, warnings
                )
                self.assertEqual(errors, [])
                self.assertIn(
                    f"{record['paths'][1]} duplicates sibling requirement text at "
                    f"{record['paths'][0]}; verify the official source (wording preserved)",
                    warnings,
                )
                self.assertEqual(project(requirements), expected)


if __name__ == "__main__":
    unittest.main()
