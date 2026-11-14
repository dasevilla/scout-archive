import re
import json

import scrapy
from scrapy import Selector

from scout_archive.items import CubScoutAdventureItem
from scout_archive.requirements_pipeline import (
    HtmlExtractor,
    MarkdownGenerator,
    RawRequirementItem,
    SemanticProcessor,
)


class CubScoutAdventuresSpider(scrapy.Spider):
    name = "cub_scout_adventures"
    allowed_domains = ["scouting.org"]
    start_urls = ["https://www.scouting.org/programs/cub-scouts/adventures/"]

    def __init__(self, name=None, url=None, **kwargs):
        self.single_url = url
        self._requirements_extractor = HtmlExtractor()
        self._requirements_processor = SemanticProcessor()
        self._requirements_generator = MarkdownGenerator()
        super().__init__(name, **kwargs)

    def parse(self, response):
        if self.single_url:
            # Determine if single URL is a rank page or adventure page
            if (
                "/programs/cub-scouts/adventures/" in self.single_url
                and self.single_url.count("/") == 5
            ):
                # This is a rank page, parse it as such
                yield scrapy.Request(self.single_url, callback=self.parse_rank)
            else:
                # This is an adventure page
                yield scrapy.Request(self.single_url, callback=self.parse_adventure)
        else:
            rank_urls = [
                f"https://www.scouting.org/programs/cub-scouts/adventures/{rank}/"
                for rank in self.settings.get("CUB_SCOUT_RANKS", [])
            ]
            for rank_url in rank_urls:
                yield scrapy.Request(rank_url, callback=self.parse_rank)

    def parse_rank(self, response):
        rank_name = response.url.split("/")[-2].replace("-", " ").title()
        if rank_name == "Arrow Of Light":
            rank_name = "Arrow of Light"

        # Regular adventure links
        adventure_links = response.css("h2 a[href*='/cub-scout-adventures/']")
        for link in adventure_links:
            adventure_url = response.urljoin(link.attrib.get("href", ""))
            yield scrapy.Request(
                adventure_url,
                callback=self.parse_adventure,
                meta={"rank_name": rank_name},
            )

        # Special Bobcat adventure link
        bobcat_links = response.css("a[href*='/cub-scout-adventures/bobcat-']")
        for link in bobcat_links:
            adventure_url = response.urljoin(link.attrib.get("href", ""))
            yield scrapy.Request(
                adventure_url,
                callback=self.parse_adventure,
                meta={"rank_name": rank_name},
            )

    def parse_adventure(self, response):
        item = CubScoutAdventureItem()

        rank_name = response.meta.get("rank_name")
        if not rank_name:
            # Extract from breadcrumb navigation
            breadcrumb_links = response.css('a[href*="/adventures/"]')
            for link in breadcrumb_links:
                link_text = link.css("::text").get()
                if link_text and link_text.strip() in [
                    "Lion",
                    "Tiger",
                    "Wolf",
                    "Bear",
                    "Webelos",
                    "Arrow of Light",
                ]:
                    rank_name = link_text.strip()
                    break

        item["rank_name"] = rank_name or "Unknown"

        adventure_name = response.css("h1.elementor-heading-title::text").get()
        if adventure_name:
            adventure_name = adventure_name.strip()
        item["adventure_name"] = adventure_name or ""

        item["adventure_url"] = response.url
        item["adventure_url_slug"] = (
            response.url.split("/")[-2]
            if response.url.endswith("/")
            else response.url.split("/")[-1]
        )

        adventure_type = ""
        adventure_category = ""
        header_spans = response.css("span.elementor-heading-title span::text").getall()
        for span_text in header_spans:
            text = span_text.strip() if span_text else ""
            if "Required" in text or "Elective" in text:
                adventure_type = text
            elif text and text not in ["Required", "Elective"] and len(text) > 3:
                adventure_category = text

        item["adventure_type"] = adventure_type
        item["adventure_category"] = adventure_category

        # Get adventure overview - skip "Adventure Snapshot" labels
        overview_paragraphs = response.xpath(
            "//h2[contains(text(), 'Snapshot of adventure')]/following::p[position() <= 3]//text()"
        ).getall()

        overview_text = ""
        if overview_paragraphs:
            full_text = " ".join(
                text.strip() for text in overview_paragraphs if text.strip()
            )
            # If it starts with "Adventure Snapshot", try to get the next meaningful content
            if full_text.startswith("Adventure Snapshot"):
                # Split by "Adventure Snapshot" and take what comes after
                parts = full_text.split("Adventure Snapshot", 1)
                if len(parts) > 1 and parts[1].strip():
                    overview_text = parts[1].strip()
            else:
                overview_text = full_text

        item["adventure_overview"] = overview_text

        # Get adventure image URL
        image_url = ""

        # Strategy 0: Prefer og/twitter meta images (most reliable)
        meta_image_url = response.css("meta[property='og:image']::attr(content)").get()
        if not meta_image_url:
            meta_image_url = response.css(
                "meta[name='twitter:image']::attr(content)"
            ).get()
        if meta_image_url:
            image_url = meta_image_url

        # Strategy 1: Look for the featured image in the Elementor config (fallback)
        script_content = response.xpath(
            "//script[contains(text(), 'elementorFrontendConfig')]/text()"
        ).get()
        if script_content and not image_url:
            try:
                # Extract the JSON object from the script content
                # Format is: var elementorFrontendConfig = {...};
                json_str = (
                    script_content.split("var elementorFrontendConfig = ", 1)[1]
                    .strip()
                    .rstrip(";")
                )
                config = json.loads(json_str)
                image_url = config.get("post", {}).get("featuredImage")
            except (IndexError, json.JSONDecodeError, AttributeError):
                self.logger.warning(
                    f"Failed to parse elementorFrontendConfig for {response.url}"
                )

        # Strategy 2: Look for a loop/pin image in the page markup
        if not image_url:
            image_sources = response.css("img::attr(data-src), img::attr(src)").getall()
            for src in image_sources:
                if src and re.search(r"loops|pins", src):
                    image_url = src
                    break

        item["adventure_image_url"] = image_url
        item["image_urls"] = [image_url] if image_url else []

        requirements_list = self.extract_requirements_summary(response, adventure_name)
        if not requirements_list:
            self.logger.warning(
                f"No summary requirements found for {adventure_name}, falling back to legacy extraction."
            )
            requirements_list = self.extract_requirements_legacy(
                response, adventure_name
            )

        item["requirements_data"] = requirements_list

        if not adventure_name:
            self.logger.error(f"No adventure name found for {response.url}")
            return

        if not requirements_list:
            self.logger.warning(
                f"No requirements found for {adventure_name} at {response.url}"
            )

        yield item

    def extract_activities_for_requirement(self, response, req_section):
        """Extract activities for a specific requirement section."""
        activities = []

        # Find the requirement section in the detailed requirements area
        req_heading = req_section.xpath("text()").get() or ""
        req_match = re.search(r"Requirement (\d+)", req_heading)

        if not req_match:
            return activities

        req_number = req_match.group(1)

        # Look for the detailed requirement section with activities
        detailed_req_xpath = f"//h2[contains(text(), 'Requirement {req_number}')]"
        detailed_req_sections = response.xpath(detailed_req_xpath)

        if not detailed_req_sections:
            return activities

        detailed_req_section = detailed_req_sections[0]

        # Find all activity cards following this requirement section
        # Activities are in article elements after the requirement heading
        activity_cards = detailed_req_section.xpath(
            "following-sibling::*//article | following::article[position() <= 10]"
        )

        for card in activity_cards:
            # Check if this card belongs to the next requirement
            next_req_heading = card.xpath(
                "preceding::h2[contains(text(), 'Requirement')][1]/text()"
            ).get()
            if next_req_heading and f"Requirement {req_number}" not in next_req_heading:
                break

            activity = self.extract_activity_data(card)
            if activity:
                activities.append(activity)

        return activities

    def extract_requirements_summary(self, response, adventure_name):
        requirements_list = []
        seen_requirements = set()

        summary_root = response.xpath(
            "//h2[contains(normalize-space(.), 'Complete the following requirements')]/ancestor::section[1]"
        )
        req_sections = summary_root.xpath(
            ".//h3[contains(normalize-space(.), 'Requirement')]"
        )

        if not req_sections:
            return []

        self.logger.info(
            f"Found {len(req_sections)} summary requirement sections for {adventure_name}"
        )

        for req_section in req_sections:
            req_match = self._match_requirement_heading(req_section)
            if not req_match:
                continue

            req_number = req_match.group(1)
            if req_number in seen_requirements:
                continue
            requirement_data = self._build_requirement_data(
                req_number=req_number,
                content=self._requirement_widget_content(req_section),
                activities=self.extract_activities_for_requirement(
                    response, req_section
                ),
            )
            if requirement_data:
                requirements_list.append(requirement_data)
                seen_requirements.add(req_number)

        return requirements_list

    def extract_requirements_legacy(self, response, adventure_name):
        requirements_list = []
        seen_requirements = set()
        req_sections = response.xpath(
            "//h2[contains(., 'Requirement')] | //h3[contains(., 'Requirement')]"
        )

        self.logger.info(
            f"Found {len(req_sections)} requirement sections for {adventure_name}"
        )

        for req_section in req_sections:
            req_match = self._match_requirement_heading(req_section)
            if not req_match:
                continue

            req_number = req_match.group(1)
            if req_number in seen_requirements:
                continue
            # Older pages can put the paragraph next to the heading or its wrapper.
            # Stay within that block so a missing paragraph cannot borrow later text.
            content = self._requirement_widget_content(req_section)
            if content is None:
                paragraphs = req_section.xpath(
                    "following-sibling::*[1][self::p]"
                    " | ../following-sibling::*[1][self::p]"
                    " | ../following-sibling::*[1][self::div]/p[1]"
                )
                content = paragraphs[0] if paragraphs else None
            requirement_data = self._build_requirement_data(
                req_number=req_number,
                content=content,
                activities=self.extract_activities_for_requirement(
                    response, req_section
                ),
            )
            if requirement_data:
                requirements_list.append(requirement_data)
                seen_requirements.add(req_number)

        return requirements_list

    @staticmethod
    def _match_requirement_heading(heading: Selector) -> re.Match[str] | None:
        return re.fullmatch(
            r"Requirement (\d+)", heading.xpath("normalize-space(.)").get("")
        )

    @staticmethod
    def _requirement_widget_content(heading: Selector) -> Selector | None:
        containers = heading.xpath(
            "ancestor::div[contains(@class, 'elementor-widget-heading')][1]"
            "/following-sibling::*[1][self::div and contains(@class, 'elementor-widget-text-editor')]"
            "//div[contains(@class, 'elementor-widget-container')][1]"
        )
        return containers[0] if containers else None

    def _build_requirement_data(
        self,
        req_number: str,
        content: Selector | None,
        activities: list[dict[str, str]],
    ) -> dict | None:
        if content is None:
            return None
        visible_text = "".join(
            content.xpath(
                ".//text()[not(ancestor::script or ancestor::style or ancestor::template)]"
            ).getall()
        )
        if not any(char.isalnum() for char in visible_text):
            return None
        content_nodes = self._requirements_extractor.extract_nodes(content.get())
        raw_item = RawRequirementItem(
            id=req_number, content_nodes=content_nodes, sub_requirements=[]
        )
        requirements = self._requirements_processor.process([raw_item])
        if not requirements:
            return None
        semantic_requirement = requirements[0]
        if not semantic_requirement.label:
            semantic_requirement.label = req_number
        semantic_requirement.requirement_path = semantic_requirement.label or req_number

        req_text = self._requirements_generator.render_content(
            semantic_requirement.content
        )
        if not any(char.isalnum() for char in req_text):
            return None

        requirement_data = semantic_requirement.model_dump()
        requirement_data["text"] = req_text
        requirement_data["activities"] = activities
        return requirement_data

    def extract_activity_data(self, card):
        """Extract activity data from an activity card element."""
        # Get activity name and URL
        title_elements = card.xpath(".//h2/a")
        if not title_elements:
            return None

        title_element = title_elements[0]

        activity = {
            "name": title_element.xpath("text()").get("").strip(),
            "url": title_element.xpath("@href").get(""),
            "description": "",
            "location": "",
            "energy_level": "",
            "supply_list": "",
            "prep_time": "",
        }

        # Get description
        desc_elements = card.xpath(".//p")
        if desc_elements:
            desc_text = " ".join(desc_elements[0].xpath(".//text()").getall())
            activity["description"] = desc_text.strip()

        # Extract metadata from icon-box elements
        # Look for elementor-icon-box-title elements which contain the metadata
        # The text is actually in nested elements, so we need to get all text
        icon_box_elements = card.css(".elementor-icon-box-title")
        metadata_values = []

        for element in icon_box_elements:
            # Get all text content from this element and its children
            all_text = element.css("::text").getall()
            for text in all_text:
                text = text.strip()
                if text and text in ["Indoor", "Outdoor", "Travel"]:
                    activity["location"] = text
                elif text and re.match(r"^\d+$", text):
                    metadata_values.append(text)

        # Assign numeric values in order: energy_level, supply_list, prep_time
        if len(metadata_values) >= 1:
            activity["energy_level"] = metadata_values[0]
        if len(metadata_values) >= 2:
            activity["supply_list"] = metadata_values[1]
        if len(metadata_values) >= 3:
            activity["prep_time"] = metadata_values[2]

        return activity
