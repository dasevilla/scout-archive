from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
from scout_archive.items import CubScoutAdventureItem
from markdownify import markdownify as md


class CubScoutAdventuresSpider(CrawlSpider):
    name = "cub_scout_adventures"
    allowed_domains = ["scouting.org"]
    start_urls = ["https://www.scouting.org/programs/cub-scouts/adventures/"]

    rules = (
        # Follow links to rank pages (e.g., Tiger, Wolf)
        Rule(
            LinkExtractor(allow=r"/programs/cub-scouts/adventures/[^/]+/$"),
            callback="parse_rank",
            follow=True,
        ),
        # Follow links to adventure requirement pages
        Rule(
            LinkExtractor(allow=r"/cub-scout-adventures/[^/]+/$"),
            callback="parse_adventure",
            follow=False,
        ),
    )

    def parse_rank(self, response):
        # This method is intentionally left blank because we're using rules to automatically follow links
        pass

    def parse_adventure(self, response):
        item = CubScoutAdventureItem()

        # Extract rank name from breadcrumb or URL
        rank_name = self.extract_rank_name(response.url)
        item["rank_name"] = rank_name

        # Extract adventure name
        adventure_name_selector = response.xpath("//h1/text()")
        if not adventure_name_selector:
            self.logger.warning(f"Adventure name not found for {response.url}")
            return

        adventure_name = adventure_name_selector.get().strip()
        item["adventure_name"] = adventure_name

        # Save page HTML
        item["page_html"] = response.text

        # Extract requirements HTML
        requirements_div = response.xpath(
            '//div[contains(@class, "elementor-widget-theme-post-content") or contains(@class, "elementor-widget-container")]'
        )
        if not requirements_div:
            self.logger.warning(f"Requirements not found for {adventure_name}")
            return

        requirements_html = "".join(requirements_div.getall())
        item["requirements_html"] = requirements_html

        # Convert requirements to Markdown
        requirements_md = md(requirements_html, heading_style="ATX")
        item["requirements_md"] = (
            f"# {adventure_name} ({rank_name}) Requirements\n\n{requirements_md}"
        )

        yield item

    def extract_rank_name(self, url):
        # Possible ranks
        ranks = ["lion", "tiger", "wolf", "bear", "webelos", "arrow-of-light"]
        for rank in ranks:
            if rank in url:
                return rank.capitalize().replace("-", " ")
        return "Unknown Rank"
