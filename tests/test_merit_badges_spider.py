import json
import sys
import tempfile
import unittest
from pathlib import Path

from scrapy.crawler import Crawler
from scrapy.downloadermiddlewares.redirect import RedirectMiddleware
from scrapy.exceptions import CloseSpider
from scrapy.http import Request, TextResponse
from scrapy.settings import Settings

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scout_archive.spiders.merit_badges import MeritBadgesSpider
from scout_archive.pipelines import ScoutArchivePipeline


def make_response(
    html: str,
    url: str = "https://www.scouting.org/merit-badges/swimming/",
    meta: dict | None = None,
) -> TextResponse:
    request = Request(url=url, meta=meta)
    return TextResponse(url=url, request=request, body=html.encode(), encoding="utf-8")


class MeritBadgesSpiderMetadataTest(unittest.TestCase):
    def setUp(self) -> None:
        self.spider = MeritBadgesSpider()

    def test_extracts_current_standard_badge_markup(self) -> None:
        response = make_response(
            """
            <html>
              <head>
                <meta property="og:title" content="Swimming Merit Badge | Scouting America">
              </head>
              <body>
                <span class="elementor-heading-title">Swimming</span>
                <div class="e-con">
                  <div class="elementor-widget-image">
                    <img src="data:image/svg+xml,%3Csvg%3E" data-src="/wp-content/uploads/2022/12/Swimming.png">
                  </div>
                </div>
                <div class="e-con">
                  <span class="elementor-heading-title">Swimming</span>
                  <span class="elementor-heading-title">Merit Badge</span>
                </div>
                <span class="elementor-heading-title">Merit Badge</span>
                <span class="elementor-heading-title">Scouting America Merit Badge Hub</span>
                <span class="elementor-heading-title">Eagle Required</span>
                <h2 class="elementor-heading-title"> Merit Badge Overview</h2>
                <div class="elementor-widget-text-editor">
                  <div class="elementor-widget-container">Learn safe swimming skills.</div>
                </div>
                <div class="mb-scoutshop-pamphlet">
                  <a href="https://www.scoutshop.org/swimming-merit-badge-pamphlet-662442.html">
                    <span>Shop Now</span>
                  </a>
                </div>
                <a href="https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Swimming.pdf">
                  <span>Download Free Pamphlet</span>
                </a>
                <div class="mb-requirement-container">
                  <div class="mb-requirement-item">
                    <div class="mb-requirement-parent mb-requirement-id-1">
                      <span class="mb-requirement-listnumber">1.</span> Do the following:
                    </div>
                  </div>
                </div>
              </body>
            </html>
            """
        )

        item = next(self.spider.parse_merit_badge(response))

        self.assertEqual(item["badge_name"], "Swimming")
        self.assertEqual(item["badge_overview"], "Learn safe swimming skills.")
        self.assertEqual(
            item["badge_pdf_url"],
            "https://filestore.scouting.org/filestore/Merit_Badge_ReqandRes/Pamphlets/Swimming.pdf",
        )
        self.assertEqual(
            item["badge_shop_url"],
            "https://www.scoutshop.org/swimming-merit-badge-pamphlet-662442.html",
        )
        self.assertEqual(
            item["badge_image_url"],
            "https://www.scouting.org/wp-content/uploads/2022/12/Swimming.png",
        )
        self.assertTrue(item["is_eagle_required"])

    def test_related_badge_eagle_text_does_not_mark_badge_eagle_required(self) -> None:
        response = make_response(
            """
            <html>
              <head><title>Canoeing Merit Badge | Scouting America</title></head>
              <body>
                <span class="elementor-heading-title">Canoeing</span>
                <span class="elementor-heading-title">Merit Badge</span>
                <h2 class="elementor-heading-title"> Merit Badge Overview</h2>
                <div class="elementor-widget-text-editor">
                  <div class="elementor-widget-container">Learn canoeing skills.</div>
                </div>
                <h2 class="elementor-heading-title">
                  <a href="/merit-badges/lifesaving/">Eagle Required</a>
                </h2>
                <div class="mb-requirement-container">
                  <div class="mb-requirement-item">
                    <div class="mb-requirement-parent mb-requirement-id-1">
                      <span class="mb-requirement-listnumber">1.</span> Do the following:
                    </div>
                  </div>
                </div>
              </body>
            </html>
            """,
            url="https://www.scouting.org/merit-badges/canoeing/",
        )

        item = next(self.spider.parse_merit_badge(response))

        self.assertEqual(item["badge_name"], "Canoeing")
        self.assertFalse(item["is_eagle_required"])

    def test_legacy_h1_badge_name_fallback_still_parses(self) -> None:
        response = make_response(
            """
            <html>
              <head><title>Scouting America</title></head>
              <body>
                <h1 class="elementor-heading-title">Legacy Merit Badge</h1>
                <div class="mb-requirement-container">
                  <div class="mb-requirement-item">
                    <div class="mb-requirement-parent mb-requirement-id-1">
                      <span class="mb-requirement-listnumber">1.</span> Do the following:
                    </div>
                  </div>
                </div>
              </body>
            </html>
            """,
            url="https://www.scouting.org/merit-badges/legacy/",
        )

        item = next(self.spider.parse_merit_badge(response))

        self.assertEqual(item["badge_name"], "Legacy")

    def test_standard_badge_without_name_fails_fast(self) -> None:
        response = make_response(
            """
            <html>
              <head><title>Scouting America</title></head>
              <body>
                <div class="mb-requirement-container"></div>
              </body>
            </html>
            """
        )

        with self.assertRaises(CloseSpider):
            list(self.spider.parse_merit_badge(response))


class MeritBadgesSpiderRetiredLabTest(unittest.TestCase):
    source_url = (
        "https://www.scouting.org/skills/merit-badges/test-lab/"
        "military-service-veterans/"
    )
    expired_html = """
        <title>Expired Content | Scouting America</title>
        <h1>Expired Content</h1>
        <h2>Thank you for your interest, but this content has been phased out.</h2>
    """

    def setUp(self) -> None:
        self.spider = MeritBadgesSpider()

    def test_retired_lab_redirect_yields_no_archive_item_and_logs_source(self) -> None:
        for url in (
            "https://www.scouting.org/expired-content/",
            "https://scouting.org/expired-content?source=test-lab",
        ):
            with self.subTest(url=url):
                response = make_response(
                    self.expired_html,
                    url=url,
                    meta={
                        "redirect_urls": [self.source_url],
                        "redirect_reasons": [301],
                    },
                )
                with self.assertLogs(self.spider.name, level="WARNING") as logs:
                    items = list(self.spider.parse_merit_badge(response, is_lab=True))
                self.assertEqual(items, [])
                self.assertIn(self.source_url, logs.output[0])
                self.assertIn(url, logs.output[0])

    dance_lab_url = "https://www.scouting.org/skills/merit-badges/test-lab/dance/"
    cub_activity_url = (
        "https://www.scouting.org/cub-scout-activities/dance-memory-grooves/"
    )
    cub_activity_html = """
        <title>Dance Memory Grooves | Scouting America</title>
        <h1 class="elementor-heading-title">Dance Memory Grooves</h1>
    """

    def test_retired_dance_redirect_does_not_archive_cub_activity(self) -> None:
        listing = make_response(
            f'<a href="{self.dance_lab_url}">Dance</a>',
            url=self.dance_lab_url.removesuffix("dance/"),
        )
        (request,) = self.spider.parse_test_lab_list(listing)
        middleware = RedirectMiddleware.from_crawler(
            Crawler(MeritBadgesSpider, Settings())
        )
        redirect = TextResponse(
            request.url,
            status=301,
            headers={"Location": self.cub_activity_url},
        )
        follow = middleware.process_response(request, redirect, self.spider)
        self.assertIsInstance(follow, Request)
        response = TextResponse(
            follow.url,
            request=follow,
            body=self.cub_activity_html.encode(),
            encoding="utf-8",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            archive = output / "dance-merit-badge.json"
            archive.write_text(json.dumps({"is_lab": True, "url": self.dance_lab_url}))
            archive.with_suffix(".md").write_text("Historical Dance requirements")
            pipeline = ScoutArchivePipeline(tmpdir, tmpdir)

            for item in follow.callback(response, **follow.cb_kwargs):
                pipeline.process_item(item, self.spider)
            self.assertTrue(archive.exists())  # Defer retirement until crawl close.
            pipeline.close_spider(self.spider)

            self.assertEqual(self.spider.expired_lab_urls, {self.dance_lab_url})
            self.assertEqual(list(output.iterdir()), [])

    def test_retired_dance_redirect_preserves_same_slug_standard_badge(self) -> None:
        response = make_response(
            self.cub_activity_html,
            url=self.cub_activity_url,
            meta={"redirect_urls": [self.dance_lab_url], "redirect_reasons": [308]},
        )
        self.assertEqual(list(self.spider.parse_merit_badge(response, is_lab=True)), [])
        self.assertEqual(self.spider.expired_lab_urls, {self.dance_lab_url})

        with tempfile.TemporaryDirectory() as tmpdir:
            archive = Path(tmpdir) / "dance-merit-badge.json"
            payload = {
                "is_lab": False,
                "url": "https://www.scouting.org/merit-badges/dance/",
            }
            archive.write_text(json.dumps(payload))
            markdown = archive.with_suffix(".md")
            markdown.write_text("Standard Dance requirements")
            ScoutArchivePipeline(tmpdir, tmpdir).close_spider(self.spider)

            self.assertEqual(json.loads(archive.read_text()), payload)
            self.assertEqual(markdown.read_text(), "Standard Dance requirements")

    def test_other_cub_activity_redirects_do_not_retire_test_labs(self) -> None:
        for sources, destination, reasons in (
            ([self.dance_lab_url], self.cub_activity_url, [302]),
            ([self.dance_lab_url], self.cub_activity_url, [307]),
            ([self.dance_lab_url], self.cub_activity_url, []),
            ([self.source_url], self.cub_activity_url, [301]),
            (
                [self.dance_lab_url],
                self.cub_activity_url.replace("www.scouting.org", "example.org"),
                [301],
            ),
            (
                [self.dance_lab_url.replace("www.scouting.org", "example.org")],
                self.cub_activity_url,
                [301],
            ),
            (
                [self.dance_lab_url],
                self.cub_activity_url.replace("dance-memory-grooves", "other-activity"),
                [301],
            ),
            ([self.dance_lab_url, self.source_url], self.cub_activity_url, [301, 302]),
        ):
            with self.subTest(
                sources=sources, destination=destination, reasons=reasons
            ):
                response = make_response(
                    self.cub_activity_html,
                    url=destination,
                    meta={"redirect_urls": sources, "redirect_reasons": reasons},
                )
                (item,) = self.spider.parse_merit_badge(response, is_lab=True)
                self.assertEqual(item["requirements_data"], [])
                self.assertEqual(self.spider.expired_lab_urls, set())

    def test_standard_badge_redirect_to_expired_page_still_fails(self) -> None:
        response = make_response(
            self.expired_html,
            url="https://www.scouting.org/expired-content/",
            meta={"redirect_urls": ["https://www.scouting.org/merit-badges/swimming/"]},
        )
        with self.assertRaises(CloseSpider):
            list(self.spider.parse_merit_badge(response))

    def test_expired_lab_archives_removed_at_crawl_close(self) -> None:
        response = make_response(
            self.expired_html,
            url="https://www.scouting.org/expired-content/",
            meta={"redirect_urls": [self.source_url]},
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            archive = Path(tmpdir) / "military-service-veterans-merit-badge.json"
            archive.write_text(json.dumps({"is_lab": True, "url": self.source_url}))
            markdown = archive.with_suffix(".md")
            markdown.write_text("Previously archived requirements")
            other_archive = Path(tmpdir) / "dance-merit-badge.json"
            other_archive.write_text("Unrelated archive")
            pipeline = ScoutArchivePipeline(tmpdir, tmpdir)

            self.assertEqual(
                list(self.spider.parse_merit_badge(response, is_lab=True)), []
            )
            self.assertTrue(archive.exists())
            pipeline.close_spider(self.spider)
            self.assertFalse(archive.exists())
            self.assertFalse(markdown.exists())
            self.assertEqual(other_archive.read_text(), "Unrelated archive")
            pipeline.close_spider(self.spider)  # Missing files are safe on repeat runs.

    def test_unconfirmed_or_replaced_archives_are_preserved(self) -> None:
        for expired_urls, payload in (
            (set(), {"is_lab": True, "url": self.source_url}),
            ({self.source_url}, {"is_lab": False, "url": self.source_url}),
            (
                {self.source_url},
                {
                    "is_lab": True,
                    "url": "https://www.scouting.org/merit-badges/military-service-veterans/",
                },
            ),
            (
                {self.source_url},
                {
                    "is_lab": True,
                    "url": "https://example.org/skills/merit-badges/test-lab/military-service-veterans/",
                },
            ),
        ):
            with self.subTest(expired_urls=expired_urls, payload=payload):
                self.spider.expired_lab_urls = expired_urls
                with tempfile.TemporaryDirectory() as tmpdir:
                    archive = (
                        Path(tmpdir) / "military-service-veterans-merit-badge.json"
                    )
                    archive.write_text(json.dumps(payload))
                    markdown = archive.with_suffix(".md")
                    markdown.write_text("Keep this archive")
                    pipeline = ScoutArchivePipeline(tmpdir, tmpdir)
                    pipeline.close_spider(self.spider)
                    self.assertEqual(json.loads(archive.read_text()), payload)
                    self.assertEqual(markdown.read_text(), "Keep this archive")

    def test_cleanup_requires_a_scouting_test_lab_source_url(self) -> None:
        for source in (
            "https://example.org/skills/merit-badges/test-lab/military-service-veterans/",
            "https://www.scouting.org/merit-badges/military-service-veterans/",
            "https://www.scouting.org/skills/merit-badges/test-lab/../military-service-veterans/",
        ):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as tmpdir:
                self.spider.expired_lab_urls = {source}
                archive = Path(tmpdir) / "military-service-veterans-merit-badge.json"
                archive.write_text(json.dumps({"is_lab": True, "url": source}))
                pipeline = ScoutArchivePipeline(tmpdir, tmpdir)
                pipeline.close_spider(self.spider)
                self.assertTrue(archive.exists())

    def test_other_broken_lab_pages_are_not_silently_skipped(self) -> None:
        for url, meta in (
            (self.source_url, {}),
            ("https://www.scouting.org/expired-content/", {}),
            (
                "https://www.scouting.org/unavailable/",
                {"redirect_urls": [self.source_url]},
            ),
            (
                "https://example.org/expired-content/",
                {"redirect_urls": [self.source_url]},
            ),
            (
                "https://www.scouting.org/expired-content/other/",
                {"redirect_urls": [self.source_url]},
            ),
        ):
            with self.subTest(url=url, meta=meta):
                response = make_response(self.expired_html, url=url, meta=meta)
                item = next(self.spider.parse_merit_badge(response, is_lab=True))
                self.assertEqual(item["badge_name"], "")
                self.assertEqual(item["requirements_data"], [])

    def test_active_lab_redirect_still_writes_json_and_markdown(self) -> None:
        response = make_response(
            """
            <h1 class="elementor-heading-title">Dance Merit Badge</h1>
            <div class="e-con">
              <h2>REQUIREMENTS</h2>
              <div class="elementor-widget-text-editor">
                <div class="elementor-widget-container">
                  <p>1. Discuss safe practices for dancing with your counselor.</p>
                  <p>2. Demonstrate a dance and explain its history.</p>
                </div>
              </div>
            </div>
            """,
            url="https://www.scouting.org/skills/merit-badges/test-lab/dance/",
            meta={"redirect_urls": [self.source_url]},
        )
        item = next(self.spider.parse_merit_badge(response, is_lab=True))
        self.assertEqual(item["badge_name"], "Dance")
        self.assertEqual(len(item["requirements_data"]), 2)
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = ScoutArchivePipeline(tmpdir, tmpdir)
            pipeline.process_item(item, self.spider)
            data = json.loads((Path(tmpdir) / "dance-merit-badge.json").read_text())
            markdown = (Path(tmpdir) / "dance-merit-badge.md").read_text()
        self.assertTrue(data["is_lab"])
        self.assertEqual(len(data["requirements"]), 2)
        self.assertIn("Discuss safe practices for dancing", markdown)
        self.assertIn("Demonstrate a dance", markdown)


if __name__ == "__main__":
    unittest.main()
