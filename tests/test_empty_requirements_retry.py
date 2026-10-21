"""Recover from empty HTTP-200 badge responses without publishing stale data."""

import re
import sys
import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup
from scrapy.crawler import Crawler
from scrapy.http import Request, TextResponse
from scrapy.settings import Settings
from scrapy.statscollectors import MemoryStatsCollector

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scout_archive.spiders.merit_badges import MeritBadgesSpider

FIXTURE = Path(__file__).parent / "fixtures/resources/composite-materials.html"
URL = "https://www.scouting.org/merit-badges/composite-materials/"
PAGE = "<title>Composite Materials Merit Badge | Scouting America</title>"


class EmptyRequirementsRetryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.output = tempfile.TemporaryDirectory()
        self.addCleanup(self.output.cleanup)
        crawler = Crawler(
            MeritBadgesSpider,
            Settings({"MERIT_BADGE_OUTPUT_DIR": self.output.name, "RETRY_TIMES": 2}),
        )
        crawler.stats = MemoryStatsCollector(crawler)
        self.spider = MeritBadgesSpider.from_crawler(crawler)

    def response(self, html: str, request: Request | None = None) -> TextResponse:
        return TextResponse(
            url=URL,
            request=request or Request(URL, callback=self.spider.parse_merit_badge),
            body=(PAGE + html).encode(),
            encoding="utf-8",
        )

    def test_empty_response_retries_and_complete_source_preserves_all_requirements(
        self,
    ) -> None:
        # The failed run saved no raw HTML. Exercise both absent markup and a
        # populated container whose only entry is the excluded pamphlet note.
        soup = BeautifulSoup(FIXTURE.read_text(), "html.parser")
        note = str(soup.select_one(".mb-requirement-item"))
        for incomplete in ("", f'<div class="mb-requirement-container">{note}</div>'):
            with self.subTest(incomplete=incomplete):
                response = self.response(incomplete)
                retry = list(self.spider.parse_merit_badge(response))
                self.assertEqual(len(retry), 1)
                request = retry[0]
                self.assertIsInstance(request, Request)
                self.assertEqual(request.url, URL)
                self.assertEqual(request.callback, response.request.callback)
                self.assertTrue(request.dont_filter)
                self.assertEqual(request.meta["retry_times"], 1)
                self.assertEqual(
                    (
                        Path(self.output.name)
                        / "extraction-failures/composite-materials-0.html"
                    ).read_bytes(),
                    response.body,
                )
                item = next(
                    self.spider.parse_merit_badge(
                        self.response(FIXTURE.read_text(), request)
                    )
                )
                requirements = item["requirements_data"]
                self.assertEqual([r["label"] for r in requirements], list("123456"))
                self.assertEqual(
                    [len(r["sub_requirements"]) for r in requirements],
                    [3, 2, 3, 2, 3, 2],
                )
                for parent in requirements:
                    children = parent["sub_requirements"]
                    self.assertEqual(
                        [child["requirement_path"] for child in children],
                        [
                            f"{parent['label']}.{label}"
                            for label in "abc"[: len(children)]
                        ],
                    )
                    for node in [parent, *children]:
                        source = soup.select_one(f".mb-requirement-id-{node['id']}")
                        text = source.get_text(" ", strip=True)
                        text = re.sub(r"^(?:\d+\.|\([a-z]\))\s*", "", text)
                        text = re.split(r"\bResources?\s*:", text, maxsplit=1)[0]
                        self.assertEqual(node["text"], " ".join(text.split()))
                        self.assertEqual(
                            [r["url"] for r in node["resources"]],
                            [a["href"] for a in source.select("a[href]")],
                        )
                        self.assertIn(
                            node["text"],
                            re.sub(r"[*_]", "", item["requirements_markdown"]),
                        )
                        for resource in node["resources"]:
                            self.assertIn(
                                resource["url"], item["requirements_markdown"]
                            )

    def test_retry_exhaustion_emits_empty_item_for_validation(self) -> None:
        request = Request(URL, callback=self.spider.parse_merit_badge)
        for attempt in range(3):
            result = list(self.spider.parse_merit_badge(self.response("", request)))
            self.assertEqual(len(result), 1)
            if attempt < 2:
                request = result[0]
                self.assertIsInstance(request, Request)
                self.assertEqual(request.meta["retry_times"], attempt + 1)
            else:
                self.assertEqual(result[0]["requirements_data"], [])
                self.assertEqual(result[0]["requirements_markdown"], "")
        self.assertEqual(self.spider.crawler.stats.get_value("retry/max_reached"), 1)
        self.assertEqual(
            len(list((Path(self.output.name) / "extraction-failures").glob("*.html"))),
            3,
        )
