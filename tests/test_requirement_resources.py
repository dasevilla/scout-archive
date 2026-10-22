import json
import sys
import unittest
from pathlib import Path

from scrapy.http import HtmlResponse, Request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scout_archive.requirements_pipeline import (
    HtmlExtractor,
    LabRequirementsExtractor,
    MarkdownGenerator,
    RawRequirementItem,
    RawTextNode,
    Resource,
    SemanticProcessor,
)
from scout_archive.spiders.merit_badges import MeritBadgesSpider

FIXTURES = Path(__file__).parent / "fixtures" / "resources"
SURVEY_URL = "https://scouting.co1.qualtrics.com/jfe/form/SV_40brLNN8LSYjUXk"


def flatten(requirements: list) -> dict:
    result = {}
    for requirement in requirements:
        result[requirement.requirement_path] = requirement
        result.update(flatten(requirement.sub_requirements))
    return result


class RequirementResourcesTest(unittest.TestCase):
    def test_official_inline_resource_markers(self) -> None:
        expected = {
            "scouting-heritage": {
                "2.b.4": ("Scout Life magazine (formerly Boys' Life)", 2)
            },
            "insect-study": {
                "4.c": ("Share your scrapbook with your counselor.", 4),
                "7.b": (
                    "Explain the advantages and disadvantages of these alternatives.",
                    2,
                ),
                "9.a": ("whether you might be interested in this career.", 2),
            },
        }
        for slug, paths in expected.items():
            with self.subTest(slug=slug):
                raw = HtmlExtractor().extract((FIXTURES / f"{slug}.html").read_text())
                requirements = SemanticProcessor().process(raw)
                by_path = flatten(requirements)
                for path, (ending, count) in paths.items():
                    requirement = by_path[path]
                    self.assertTrue(requirement.text.endswith(ending), requirement.text)
                    self.assertNotIn("Resources:", requirement.text)
                    self.assertEqual(len(requirement.resources), count)
                    self.assertTrue(
                        all(r.type == "video" for r in requirement.resources)
                    )
                    self.assertTrue(
                        all(r.url.startswith("https://") for r in requirement.resources)
                    )
                    for resource in requirement.resources:
                        self.assertNotIn(resource.title, requirement.text)
                        self.assertIn(
                            resource.url, MarkdownGenerator().generate(requirements)
                        )

    def test_resources_do_not_swallow_later_requirement_prose(self) -> None:
        extractor = HtmlExtractor()
        raw = RawRequirementItem(
            id="test",
            content_nodes=extractor.extract_nodes(
                'Explain your observations.Resources: <a href="https://youtu.be/test">Guide (video)</a>'
                "<p>Discuss the results with your counselor.</p>"
                '<p>Use <a href="https://example.org/tool">this tool</a> to record the results.</p>'
            ),
        )
        requirement = SemanticProcessor().process([raw])[0]
        self.assertIn("Explain your observations.", requirement.text)
        self.assertIn("Discuss the results with your counselor.", requirement.text)
        self.assertIn("Use this tool to record the results.", requirement.text)
        self.assertEqual(
            [r.title for r in requirement.resources], ["Guide (video)", "this tool"]
        )

    def test_resource_marker_split_across_formatting(self) -> None:
        raw = RawRequirementItem(
            id="test",
            content_nodes=HtmlExtractor().extract_nodes(
                "Explain the right gear.<br><em>Resources</em>:<br>"
                '<a href="https://example.org/gear">Gear guide</a>'
            ),
        )
        requirement = SemanticProcessor().process([raw])[0]
        self.assertEqual(requirement.text, "Explain the right gear.")
        self.assertEqual(requirement.resources[0].title, "Gear guide")

    def test_resource_types(self) -> None:
        for title, url, kind in [
            ("Video", "https://youtu.be/abc", "video"),
            ("Paper", "https://example.org/guide.pdf?download=1", "document"),
            ("Go to Survey", SURVEY_URL, "survey"),
            ("History (website)", "https://example.org/history", "website"),
            ("Insects ( video)", "https://example.org/insects", "video"),
        ]:
            with self.subTest(title=title):
                self.assertEqual(Resource(title=title, url=url).type, kind)

    def test_lab_survey_button_outside_requirement_widgets(self) -> None:
        for slug, number in [("auctioneering", 9), ("physics", 9), ("psychology", 8)]:
            with self.subTest(slug=slug):
                instruction = (
                    "Complete the survey below to complete the test lab requirements"
                )
                html = f"""
                <h1>{slug.title()}</h1><div class="e-con">
                  <h2>{slug.upper()} REQUIREMENTS</h2>
                  <div class="elementor-widget-text-editor"><div class="elementor-widget-container">
                    <p><strong>1. Discuss the topic with your counselor.</strong></p>
                    <p><strong>{number}. {instruction}</strong></p>
                  </div></div>
                  <div class="elementor-widget-button"><a class="elementor-button" href="{SURVEY_URL}">
                    <span><span>Go to Survey</span></span>
                  </a></div>
                </div>"""
                response = HtmlResponse(
                    url=f"https://www.scouting.org/skills/merit-badges/test-lab/{slug}/",
                    body=html.encode(),
                    encoding="utf-8",
                    request=Request(
                        f"https://www.scouting.org/skills/merit-badges/test-lab/{slug}/"
                    ),
                )
                item = next(MeritBadgesSpider().parse_merit_badge(response))
                survey = item["requirements_data"][-1]
                self.assertEqual(survey["text"], instruction)
                self.assertEqual(
                    survey["resources"],
                    [{"title": "Go to Survey", "url": SURVEY_URL, "type": "survey"}],
                )
                self.assertEqual(item["requirements_data"][0]["resources"], [])
                self.assertIn(SURVEY_URL, item["requirements_markdown"])

    def test_missing_survey_link_is_not_invented(self) -> None:
        requirements = SemanticProcessor().process(
            [
                RawRequirementItem(
                    id="9",
                    content_nodes=HtmlExtractor().extract_nodes(
                        "9. Complete the survey below to complete the test lab requirements"
                    ),
                )
            ]
        )
        response = HtmlResponse(
            url="https://www.scouting.org/test/", body=b"<html></html>"
        )
        MeritBadgesSpider()._attach_lab_survey(response, requirements)
        self.assertEqual(requirements[0].resources, [])


class ResourceBoundaryRegressionTest(unittest.TestCase):
    def test_cybersecurity_suggestions_and_support_groups(self) -> None:
        raw = HtmlExtractor().extract((FIXTURES / "cybersecurity.html").read_text())
        nodes = flatten(SemanticProcessor().process(raw))
        media = nodes["4.e.2"]
        self.assertEqual(
            media.text,
            "With your parent or guardian's permission, watch a movie or read a book in which cybersecurity plays a significant role. Discuss how cybersecurity topics were depicted and how realistic you think it was.",
        )
        self.assertEqual(
            [r.category for r in media.resources],
            ["Suggested Movies", "Suggested Books"],
        )
        self.assertTrue(
            all(r.type == "reference" and r.url == "" for r in media.resources)
        )
        self.assertIn("WarGames (1983, PG)", media.resources[0].title)
        self.assertTrue(
            media.resources[1].title.endswith("City Spies series by James Ponti.")
        )
        support = nodes["5.c.7"]
        self.assertEqual(
            support.text,
            "Demonstrate how to back up your data from a mobile device to a local computer or the cloud.",
        )
        self.assertEqual(
            [r.category for r in support.resources], ["Apple"] * 3 + ["Android"] * 2
        )
        self.assertEqual(len(nodes), 50)
        markdown = MarkdownGenerator().generate(SemanticProcessor().process(raw))
        self.assertIn("Suggested Movies: WarGames", markdown)
        self.assertNotIn("]()", markdown)
        self.assertIn("Apple: [How to Back Up With iCloud", markdown)

    def test_release141_life_skills_standalone_links(self) -> None:
        archive = json.loads((FIXTURES / "life-skills.release141.json").read_text())
        for node in flatten_archive(archive["requirements"]):
            raw = RawRequirementItem(
                id=node["id"],
                content_nodes=[
                    RawTextNode(value=f"{node['label']}. "),
                    *node["content"],
                ],
            )
            result = SemanticProcessor().process([raw])[0]
            if node["requirement_path"] in {
                "2.a",
                "2.b",
                "2.c",
                "2.d",
                "2.e",
                "4.a",
                "4.b",
                "4.c",
                "4.d",
                "5.a",
                "5.c",
                "7.a",
                "7.b",
                "7.c",
                "7.d",
            }:
                with self.subTest(path=node["requirement_path"]):
                    self.assertEqual(result.text, node["text"].split("\n")[0])
                    self.assertTrue(result.resources)
                    self.assertTrue(
                        all(r.title not in result.text for r in result.resources)
                    )
            elif node["requirement_path"] == "5.b":
                # This link is inline, without a source resource marker or line break.
                self.assertIn("Stress Management", result.text)

    def test_lab_resource_suffix_and_instruction_protection(self) -> None:
        fixtures = FIXTURES.parent / "hierarchy"
        for slug, count in [("dance", 38), ("sewing-needlework", 81)]:
            from bs4 import BeautifulSoup

            blocks = BeautifulSoup(
                (fixtures / f"{slug}.html").read_text(), "html.parser"
            ).select(".elementor-widget-container")
            requirements = LabRequirementsExtractor().extract_from_blocks(
                [str(b) for b in blocks]
            )
            nodes = flatten(requirements)
            self.assertEqual(len(nodes), count)
            if slug == "dance":
                self.assertNotIn("(video)", nodes["6.b"].text)
                self.assertEqual(len(nodes["6.b"].resources), 2)
                self.assertEqual(nodes["6.b"].resources[0].type, "video")
                self.assertIn(
                    "What accommodations would that person need", nodes["4.e"].text
                )

    def test_notes_and_inline_links_remain_instructional(self) -> None:
        html = (
            'Use <a href="https://example.org/tool">this tool</a> to record results.'
            '<br><strong><a href="https://example.org/guide">Guide</a></strong>'
            "<br>Note: Discuss limitations with your counselor."
            '<br>Resources: <a href="https://example.org/video">Film</a> (video)'
            "<p>Suggested Books: Read a book and explain your choice.</p>"
        )
        result = SemanticProcessor().process(
            [
                RawRequirementItem(
                    id="1", content_nodes=HtmlExtractor().extract_nodes(html)
                )
            ]
        )[0]
        self.assertIn("Use this tool to record results.", result.text)
        self.assertIn("Note: Discuss limitations with your counselor.", result.text)
        # A prose paragraph is retained even if it uses a resource-like phrase.
        self.assertIn("Read a book and explain your choice.", result.text)
        self.assertNotIn("Guide", result.text)
        self.assertNotIn("(video)", result.text)
        self.assertEqual(
            Resource(title="Guide", url="https://example.org").model_dump(),
            {"title": "Guide", "url": "https://example.org", "type": "website"},
        )

    def test_unlabeled_governed_and_action_links_stay_in_prose(self) -> None:
        for html, retained in [
            (
                'Discuss the following:<br><a href="https://example.org/topic">Conservation</a>',
                "Conservation",
            ),
            (
                'Discuss safety.<br><a href="https://example.org/course">Complete this course</a>',
                "Complete this course",
            ),
        ]:
            with self.subTest(html=html):
                result = SemanticProcessor().process(
                    [
                        RawRequirementItem(
                            id="1", content_nodes=HtmlExtractor().extract_nodes(html)
                        )
                    ]
                )[0]
                self.assertIn(retained, result.text)


def flatten_archive(nodes: list[dict]) -> list[dict]:
    result = []
    for node in nodes:
        result.append(node)
        result.extend(flatten_archive(node["sub_requirements"]))
    return result
