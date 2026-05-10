import sys
import unittest
from pathlib import Path

from scrapy.exceptions import CloseSpider
from scrapy.http import Request, TextResponse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scout_archive.spiders.merit_badges import MeritBadgesSpider


def make_response(
    html: str, url: str = "https://www.scouting.org/merit-badges/swimming/"
) -> TextResponse:
    request = Request(url=url)
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


if __name__ == "__main__":
    unittest.main()
