import re
import json

import scrapy

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

        # Strategy 1: Look for the featured image in the Elementor config (Most reliable)
        script_content = response.xpath(
            "//script[contains(text(), 'elementorFrontendConfig')]/text()"
        ).get()
        if script_content:
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

        # Strategy 2: Look for the main image in the elementor widget (Fallback)
        if not image_url:
            # The structure usually has a div with class elementor-widget-image
            # We try to avoid the logo by checking for specific classes or position if possible,
            # but for now we just take the first one that isn't the logo if we can distinguish.
            # Since the logo is also an elementor-widget-image, we might need to be careful.
            # However, usually the featured image is unique in some way.
            # Let's try to find an image that is NOT the logo.
            images = response.css("div.elementor-widget-image img")
            for img in images:
                src = img.attrib.get("data-src") or img.attrib.get("src")
                if src and "scouting-america-logo" not in src:
                    image_url = src
                    break

            # If we still haven't found one, just take the first one as a last resort
            if not image_url and images:
                image_url = images[0].attrib.get("data-src") or images[0].attrib.get(
                    "src"
                )

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
            req_heading = req_section.xpath("text()").get() or ""
            req_match = re.search(r"Requirement (\d+)", req_heading)

            if not req_match:
                continue

            req_number = req_match.group(1)
            if req_number in seen_requirements:
                continue
            seen_requirements.add(req_number)

            text_container = req_section.xpath(
                "ancestor::div[contains(@class, 'elementor-element') and contains(@class, 'elementor-widget-heading')][1]"
                "/following-sibling::div[contains(@class, 'elementor-widget-text-editor')][1]"
                "//div[contains(@class, 'elementor-widget-container')][1]"
            )

            requirement_html = text_container.get() if text_container else ""
            fallback_text = " ".join(
                text_container.xpath(".//text()").getall() if text_container else []
            ).strip()

            activities = self.extract_activities_for_requirement(response, req_section)
            requirement_data = self._build_requirement_data(
                req_number=req_number,
                requirement_html=requirement_html,
                fallback_text=fallback_text,
                activities=activities,
            )
            if requirement_data:
                requirements_list.append(requirement_data)

        return requirements_list

    def extract_requirements_legacy(self, response, adventure_name):
        requirements_list = []
        seen_requirements = set()
        req_sections = response.xpath(
            "//h2[contains(text(), 'Requirement')] | //h3[contains(text(), 'Requirement')]"
        )

        self.logger.info(
            f"Found {len(req_sections)} requirement sections for {adventure_name}"
        )

        for req_section in req_sections:
            req_heading = req_section.xpath("text()").get() or ""
            req_match = re.search(r"Requirement (\d+)", req_heading)

            if not req_match:
                continue

            req_number = req_match.group(1)
            if req_number in seen_requirements:
                continue
            seen_requirements.add(req_number)

            req_text_parts = []

            if not req_text_parts:
                req_text_parts = req_section.xpath(
                    "following-sibling::p[1]//text()"
                ).getall()

            if not req_text_parts:
                req_text_parts = req_section.xpath(
                    "../following-sibling::p[1]//text()"
                ).getall()

            if not req_text_parts:
                req_text_parts = req_section.xpath(
                    "parent::*/following-sibling::*/p[1]//text()"
                ).getall()

            if not req_text_parts:
                req_text_parts = req_section.xpath("following::p[1]//text()").getall()

            fallback_text = " ".join(
                text.strip() for text in req_text_parts if text.strip()
            )

            activities = self.extract_activities_for_requirement(response, req_section)
            requirement_data = self._build_requirement_data(
                req_number=req_number,
                requirement_html=fallback_text,
                fallback_text=fallback_text,
                activities=activities,
            )
            if requirement_data:
                requirements_list.append(requirement_data)
            else:
                self.logger.warning(
                    f"Requirement {req_number} too short: '{fallback_text}'"
                )

        return requirements_list

    def _build_requirement_data(
        self, req_number, requirement_html, fallback_text, activities
    ):
        content_html = requirement_html or fallback_text or ""
        content_nodes = self._requirements_extractor.extract_nodes(content_html)
        raw_item = RawRequirementItem(
            id=req_number, content_nodes=content_nodes, sub_requirements=[]
        )
        semantic_requirement = self._requirements_processor.process([raw_item])[0]
        if not semantic_requirement.label:
            semantic_requirement.label = req_number

        req_text = self._requirements_generator.render_content(
            semantic_requirement.content
        )
        if not req_text and fallback_text:
            req_text = fallback_text

        min_words = self.settings.get("MIN_REQUIREMENT_WORDS", 5)
        if not req_text or len(req_text.split()) < min_words:
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
