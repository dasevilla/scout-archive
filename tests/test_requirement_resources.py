import sys
import unittest
from pathlib import Path

from scrapy.http import HtmlResponse, Request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scout_archive.requirements_pipeline import (
    HtmlExtractor,
    MarkdownGenerator,
    RawRequirementItem,
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
