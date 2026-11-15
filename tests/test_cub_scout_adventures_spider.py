import unittest

from scrapy import Request
from scrapy.http import HtmlResponse
from scrapy.settings import Settings

from scout_archive.items import CubScoutAdventureItem
from scout_archive.spiders.cub_scout_adventures import CubScoutAdventuresSpider


class CubScoutAdventuresSpiderTest(unittest.TestCase):
    def parse_adventure(self, html: str) -> CubScoutAdventureItem:
        url = "https://www.scouting.org/cub-scout-adventures/germs-alive/"
        response = HtmlResponse(
            url=url,
            body=(
                '<h1 class="elementor-heading-title">Germs Alive!</h1>' + html
            ).encode(),
            encoding="utf-8",
            request=Request(url, meta={"rank_name": "Wolf"}),
        )
        spider = CubScoutAdventuresSpider()
        spider.settings = Settings()
        return next(spider.parse_adventure(response))

    def parse_requirements(self, html: str) -> list[dict]:
        return self.parse_adventure(html)["requirements_data"]

    def test_overview_stays_within_snapshot_widget(self) -> None:
        adventure = self.parse_adventure("""
            <section>
              <div class="elementor-widget-heading"><h2>Snapshot of adventure</h2></div>
              <div class="elementor-widget-text-editor">
                <div class="elementor-widget-container">
                  <p>Explore how to keep your body healthy.</p>
                  <p>Find out why washing your hands matters.</p>
                </div>
              </div>
              <div class="elementor-widget-heading"><h3>Safety Moment</h3></div>
              <div class="elementor-widget-text-editor">
                <div class="elementor-widget-container"><p>Review the SAFE Checklist.</p></div>
              </div>
            </section>
        """)
        self.assertEqual(
            adventure["adventure_overview"],
            "Explore how to keep your body healthy. Find out why washing your hands matters.",
        )

    def test_short_numbered_requirements_keep_their_activity_cards(self) -> None:
        requirements = self.parse_requirements("""
            <section>
              <h2>Complete the following requirements</h2>
              <div class="elementor-element elementor-widget-heading"><h3>Requirement 3</h3></div>
              <div class="elementor-widget-text-editor">
                <div class="elementor-widget-container"><p>Conduct the sneeze demonstration.</p></div>
              </div>
              <div class="elementor-element elementor-widget-heading"><h3>Requirement 4</h3></div>
              <div class="elementor-widget-text-editor">
                <div class="elementor-widget-container"><p>Conduct the mucus demonstration.</p></div>
              </div>
            </section>
            <section>
              <h2>Requirement 3</h2>
              <article><h2><a href="/cub-scout-activities/sneeze-splosion/">Sneeze-splosion!</a></h2></article>
            </section>
            <section>
              <h2>Requirement 4</h2>
              <article><h2><a href="/cub-scout-activities/mucus-tastic/">Mucus-tastic</a></h2></article>
            </section>
        """)
        self.assertEqual(
            [
                (r["label"], r["text"], [a["name"] for a in r["activities"]])
                for r in requirements
            ],
            [
                ("3", "Conduct the sneeze demonstration.", ["Sneeze-splosion!"]),
                ("4", "Conduct the mucus demonstration.", ["Mucus-tastic"]),
            ],
        )

    def test_summary_rejects_missing_and_non_text_blocks(self) -> None:
        requirements = self.parse_requirements("""
            <section>
              <h2>Complete the following requirements</h2>
              <div class="elementor-element elementor-widget-heading"><h3>Requirement 1</h3></div>
              <div class="elementor-element elementor-widget-heading"><h3>Requirement 2</h3></div>
              <div class="elementor-widget-text-editor">
                <div class="elementor-widget-container"><p>Share your findings.</p></div>
              </div>
              <div class="elementor-element elementor-widget-heading"><h3>Requirement 3</h3></div>
              <div class="elementor-widget-text-editor">
                <div class="elementor-widget-container"><!-- Draft --><script>setup()</script><p>&nbsp;</p></div>
              </div>
              <div class="elementor-element elementor-widget-heading"><h3>Requirement 4</h3></div>
              <div class="elementor-widget-text-editor">
                <div class="elementor-widget-container"><p>&nbsp;</p></div>
              </div>
            </section>
        """)
        self.assertEqual(
            [(r["label"], r["text"]) for r in requirements],
            [("2", "Share your findings.")],
        )

    def test_legacy_requires_an_adjacent_instruction(self) -> None:
        requirements = self.parse_requirements("""
            <section>
              <h2>About Requirement 1</h2><p>Read more.</p>
              <h2>Requirement 2</h2>
              <h2>Requirement 3</h2><p>Keep a journal.</p>
              <h2>Requirement 4</h2><p>&nbsp;</p>
            </section>
            <footer><p>Visit the Scout Shop for more information.</p></footer>
        """)
        self.assertEqual(
            [(r["label"], r["text"]) for r in requirements], [("3", "Keep a journal.")]
        )
