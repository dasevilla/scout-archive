import sys
import unittest
from pathlib import Path
from typing import Iterator

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scout_archive.requirements_pipeline import (
    HtmlExtractor,
    LabRequirementsExtractor,
    MarkdownGenerator,
    SemanticProcessor,
    SemanticRequirement,
)

FIXTURES = Path(__file__).parent / "fixtures" / "hierarchy"


def walk(nodes: list[SemanticRequirement]) -> Iterator[SemanticRequirement]:
    for node in nodes:
        yield node
        yield from walk(node.sub_requirements)


def extract(name: str, lab: bool = False) -> list[SemanticRequirement]:
    html = (FIXTURES / f"{name}.html").read_text()
    if lab:
        blocks = BeautifulSoup(html, "html.parser").select(
            ".elementor-widget-container"
        )
        return LabRequirementsExtractor().extract_from_blocks([str(b) for b in blocks])
    return SemanticProcessor().process(HtmlExtractor().extract(html))


class VisualAuditHierarchyTest(unittest.TestCase):
    def test_plant_alternatives_follow_official_parent_ids(self) -> None:
        requirements = extract("plant-science")
        nodes = {node.requirement_path: node for node in walk(requirements)}
        for path, headings, counts in (
            (
                "8.option-a.5",
                ["Corn", "Cotton", "Forage Crops", "Small Grains", "Oil Crops"],
                [3, 3, 3, 3, 3],
            ),
            (
                "8.option-b.5",
                [
                    "Bedding Plants",
                    "Fruit, Berry, and Nut Crops",
                    "Woody Ornamentals",
                    "Home Gardening",
                ],
                [4, 4, 5, 4],
            ),
            (
                "8.option-c.6",
                [
                    "Tree Inventory",
                    "Transect Study",
                    "Nested Plot",
                    "Herbarium Visit",
                    "Plant Conservation Organization Visit",
                ],
                [4, 3, 3, 4, 3],
            ),
        ):
            parent = nodes[path]
            self.assertEqual(parent.node_kind, "instruction_container")
            self.assertFalse(parent.requires_response)
            self.assertEqual([n.text for n in parent.sub_requirements], headings)
            for option, count in zip(parent.sub_requirements, counts):
                self.assertEqual(option.node_kind, "option_container")
                self.assertTrue(option.is_container)
                self.assertFalse(option.requires_response)
                self.assertEqual(
                    [n.label for n in option.sub_requirements],
                    [str(i) for i in range(1, count + 1)],
                )
        self.assertEqual(
            [n.label for n in nodes["8.option-c.6.c.3"].sub_requirements],
            ["a", "b", "c"],
        )
        self.assertEqual(nodes["8.option-c.6.d"].id, "15344")
        # Every source ID must survive once, including compound labels (5)(a).
        source = BeautifulSoup(
            (FIXTURES / "plant-science.html").read_text(), "html.parser"
        )
        source_ids = [
            c.removeprefix("mb-requirement-id-")
            for t in source.select(".mb-requirement-parent, .mb-requirement-child")
            for c in t.get("class", [])
            if c.startswith("mb-requirement-id-")
        ]
        self.assertCountEqual([n.id for n in nodes.values()], source_ids)
        self.assertEqual(len(nodes), len(list(walk(requirements))))
        markdown = MarkdownGenerator().generate(requirements)
        self.assertIn("      - (c) **Nested Plot**", markdown)
        self.assertIn("        - (1) Visit two sites", markdown)

    def test_cooking_food_groups_are_five_governed_children(self) -> None:
        root = extract("cooking")[0]
        self.assertEqual([n.label for n in root.sub_requirements], list("abcde"))
        nutrition = root.sub_requirements[0]
        self.assertEqual(nutrition.id, "12839")
        self.assertEqual(
            [n.requirement_path for n in nutrition.sub_requirements],
            [f"2.a.{i}" for i in range(1, 6)],
        )
        self.assertEqual(
            [n.text for n in nutrition.sub_requirements],
            ["Fruits", "Vegetables", "Grains", "Proteins", "Dairy"],
        )
        self.assertIn("recommended serving size:", nutrition.text)
        self.assertEqual(nutrition.resources[0].title, "MyPlate Food Groups (website)")

    def test_dance_has_all_styles_and_lettered_research_and_performance(self) -> None:
        nodes = {n.requirement_path: n for n in walk(extract("dance", lab=True))}
        self.assertEqual(
            [n.label for n in nodes["3"].sub_requirements], list("abcdefghijklmno")
        )
        self.assertEqual(nodes["3.a"].text, "Acrobatics/Acro Dance")
        self.assertEqual(nodes["3.o"].text, "Tap dance")
        self.assertEqual(
            [n.label for n in nodes["4"].sub_requirements], list("abcdefg")
        )
        self.assertEqual(
            [n.label for n in nodes["5"].sub_requirements if n.text], ["a", "b"]
        )
        self.assertIn("minimum of 2 minutes", nodes["5.a"].text)
        self.assertIn("5 Elements of Dance", nodes["5.b"].text)
        # Resource extraction must preserve the hobby alternative that follows
        # career resource links within the same source list item.
        self.assertEqual([n.label for n in nodes["6"].sub_requirements], ["a", "b"])
        self.assertIn("pursue a hobby", nodes["6.b"].text)

    def test_sewing_preserves_six_crafts_and_every_lettered_prompt(self) -> None:
        nodes = {
            n.requirement_path: n for n in walk(extract("sewing-needlework", lab=True))
        }
        self.assertEqual([n.label for n in nodes["2"].sub_requirements], list("abcdef"))
        crafts = nodes["3"].sub_requirements
        self.assertEqual([n.label for n in crafts], list("ABCDEF"))
        self.assertEqual(
            [n.text for n in crafts],
            [
                "Machine Sewing",
                "Knitting",
                "Crochet",
                "Hand Embroidery",
                "Appliqué",
                "Quilting",
            ],
        )
        for craft, count in zip(crafts, [5, 5, 5, 3, 4, 5]):
            self.assertEqual(craft.node_kind, "option_container")
            self.assertFalse(craft.requires_response)
            self.assertEqual(
                [n.label for n in craft.sub_requirements], list("abcde"[:count])
            )
        self.assertEqual(len(nodes["3.a.c"].sub_requirements), 6)
        self.assertEqual(len(nodes["3.f.e"].sub_requirements), 5)
        self.assertEqual([n.label for n in nodes["6"].sub_requirements], ["a", "b"])

    def test_physics_keeps_topics_and_career_hobby_options_separate(self) -> None:
        nodes = {n.requirement_path: n for n in walk(extract("physics", lab=True))}
        self.assertEqual([n.label for n in nodes["5"].sub_requirements], list("abcd"))
        self.assertEqual([n.label for n in nodes["8"].sub_requirements], ["a", "b"])
        self.assertIn("pursue a hobby", nodes["8.b"].text)
        for option in nodes["6"].sub_requirements:
            self.assertEqual([n.label for n in option.sub_requirements], ["a", "b"])

    def test_parent_references_cannot_create_cycles(self) -> None:
        html = """<div class="mb-requirement-item"><div class="mb-requirement-parent mb-requirement-id-1">1. Do the following:</div><ul class="mb-requirement-children-list"><li class="mb-requirement-child mb-requirement-id-2 mb-parent-3">(a) Explain the tools.</li><li class="mb-requirement-child mb-requirement-id-3 mb-parent-2">(1) Describe safe use.</li></ul></div>"""
        result = SemanticProcessor().process(HtmlExtractor().extract(html))
        self.assertEqual([n.id for n in walk(result)], ["1", "2", "3"])


if __name__ == "__main__":
    unittest.main()
