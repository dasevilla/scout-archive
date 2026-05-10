import re
from urllib.parse import urlparse

import scrapy
from scrapy.exceptions import CloseSpider

from scout_archive.items import MeritBadgeItem
from scout_archive.requirements_pipeline import (
    HtmlExtractor,
    LabRequirementsExtractor,
    MarkdownGenerator,
    SemanticProcessor,
)
from scout_archive.settings import MIN_BADGE_COUNT


class MeritBadgesSpider(scrapy.Spider):
    name = "merit_badges"
    allowed_domains = ["scouting.org", "usscouts.org"]
    start_urls = ["https://www.scouting.org/skills/merit-badges/all/"]

    def __init__(self, name=None, url=None, labs_only=None, **kwargs):
        self.single_url = url
        self.labs_only = str(labs_only).lower() == "true" if labs_only else False
        self.workbook_links = {}
        self._requirements_extractor = HtmlExtractor()
        self._requirements_processor = SemanticProcessor()
        self._requirements_generator = MarkdownGenerator()
        self._lab_requirements_extractor = LabRequirementsExtractor(
            extractor=self._requirements_extractor,
            processor=self._requirements_processor,
        )
        super().__init__(name, **kwargs)

    def start_requests(self):
        yield scrapy.Request(
            "http://usscouts.org/mb/worksheets/list.asp",
            callback=self.parse_worksheets,
            errback=self.handle_worksheets_error,
        )

    def handle_worksheets_error(self, failure):
        self.logger.error(f"Failed to fetch worksheets: {failure}")
        yield from self.start_main_crawl()

    def start_main_crawl(self):
        if self.single_url:
            is_lab = "/test-lab/" in self.single_url
            yield scrapy.Request(
                self.single_url,
                callback=self.parse_merit_badge,
                cb_kwargs={"is_lab": is_lab},
            )
        else:
            if not self.labs_only:
                for url in self.start_urls:
                    yield scrapy.Request(url, callback=self.parse_start_url_custom)

            yield scrapy.Request(
                "https://www.scouting.org/skills/merit-badges/test-lab/",
                callback=self.parse_test_lab_list,
            )

    def parse_start_url_custom(self, response):
        urls = self._discover_standard_badge_urls(response)
        self.logger.info("Discovered %s standard merit badge URLs", len(urls))
        if len(urls) < MIN_BADGE_COUNT:
            raise CloseSpider(
                f"Only discovered {len(urls)} standard merit badge URLs, "
                f"expected at least {MIN_BADGE_COUNT}"
            )

        for url in urls:
            yield response.follow(url, callback=self.parse_merit_badge)

    def parse_test_lab_list(self, response):
        links = response.css(
            "a[href*='/skills/merit-badges/test-lab/']::attr(href)"
        ).getall()
        seen = set()
        discovered_count = 0
        for link in links:
            absolute = response.urljoin(link)
            if absolute.rstrip("/") == response.url.rstrip("/"):
                continue
            if not re.search(r"/skills/merit-badges/test-lab/[^/]+/?$", absolute):
                continue
            if absolute in seen:
                continue
            seen.add(absolute)
            discovered_count += 1
            yield response.follow(
                absolute, callback=self.parse_merit_badge, cb_kwargs={"is_lab": True}
            )
        self.logger.info("Discovered %s Test Lab merit badge URLs", discovered_count)

    def _discover_standard_badge_urls(
        self, response: scrapy.http.Response
    ) -> list[str]:
        urls = set()
        for href in response.css("a[href*='/merit-badges/']::attr(href)").getall():
            absolute = response.urljoin(href).split("#", 1)[0]
            parsed = urlparse(absolute)
            if parsed.netloc not in {"www.scouting.org", "scouting.org"}:
                continue
            if not re.fullmatch(r"/merit-badges/[^/]+/?", parsed.path):
                continue
            if "/test-lab/" in parsed.path:
                continue
            normalized = parsed._replace(
                path=parsed.path.rstrip("/") + "/", query="", fragment=""
            ).geturl()
            urls.add(normalized)
        return sorted(urls)

    def parse_worksheets(self, response):
        # Extract workbook links
        # The table has rows with columns: ID, Scoutbook ID, Name, Updated, DOCX, PDF, Pages
        # We look for links ending in .docx or .pdf

        # Iterate over all rows in the main table
        # We can find rows that have a DOCX or PDF link
        for row in response.css("table tr"):
            links = row.css("a")
            if not links:
                continue

            # Try to find the name and links
            name = None
            docx_url = None
            pdf_url = None

            # Usually the name is the first link, or in the first few columns
            # But the structure is a bit loose.
            # Let's look for a cell with a link to mbXX.asp or similar for the name,
            # OR just use the text of the first cell?
            # From browser inspection: Name is in column 3 (index 2), has link to ../mb001.asp
            # DOCX is in col 5, PDF in col 6.

            cells = row.css("td")
            if len(cells) < 3:
                continue

            # Attempt to extract name from the cell that has the merit badge page link (usually col 3)
            # The name might be just text or a link
            # Let's heuristic: find the cell with the badge name
            # It's usually the one with a link to "../mbXXX.asp" or similar, or just text.
            # However, simpler approach:
            # The Name col text is the key.
            # DOCX link text is often "Camping.docx". PDF is "Camping.pdf".

            # Let's iterate cells and find links
            for link in links:
                href = link.attrib.get("href", "")

                lower_href = href.lower()
                if lower_href.endswith(".docx") or lower_href.endswith(".doc"):
                    docx_url = response.urljoin(href)
                elif lower_href.endswith(".pdf"):
                    pdf_url = response.urljoin(href)

            # If we found at least one workbook link, we need a name
            if docx_url or pdf_url:
                # Consider link text as possible badge name
                possible_names = []
                for link in links:
                    href = link.attrib.get("href", "")
                    lower_href = href.lower()
                    if not (
                        lower_href.endswith(".docx")
                        or lower_href.endswith(".doc")
                        or lower_href.endswith(".pdf")
                    ):
                        link_text = link.css("::text").get()
                        if link_text:
                            possible_names.append(" ".join(link_text.split()))

                if possible_names:
                    # Taking the first non-document link as name
                    name = possible_names[0]

                    # Normalize name for storage
                    # Remove "Merit Badge" from name if present (though usually not there on usscouts)
                    clean_name = name.replace("Merit Badge", "").strip()

                    if clean_name not in self.workbook_links:
                        self.workbook_links[clean_name] = {}

                    if docx_url:
                        self.workbook_links[clean_name]["docx"] = docx_url
                    if pdf_url:
                        self.workbook_links[clean_name]["pdf"] = pdf_url

        self.logger.info(
            f"Loaded {len(self.workbook_links)} workbook entries from usscouts.org"
        )

        yield from self.start_main_crawl()

    def parse(self, response):
        # If a single URL was provided, use that instead of crawling
        if self.single_url:
            is_lab = "/test-lab/" in self.single_url
            yield scrapy.Request(
                self.single_url,
                callback=self.parse_merit_badge,
                cb_kwargs={"is_lab": is_lab},
            )
        else:
            # Grab every merit badge URL
            yield from self.parse_start_url_custom(response)

    def parse_merit_badge(self, response, is_lab=False):
        if not is_lab and "/test-lab/" in response.url:
            is_lab = True
        item = MeritBadgeItem()
        item["is_lab"] = is_lab

        item["badge_name"] = self._extract_badge_name(response, is_lab=is_lab)
        if not is_lab and not item["badge_name"]:
            raise CloseSpider(
                f"Unable to extract merit badge name from standard badge page: {response.url}"
            )

        item["badge_overview"] = self._extract_badge_overview(response)

        # Get badge URL
        item["badge_url"] = response.url

        # Get badge URL slug
        item["badge_url_slug"] = response.url.split("/")[-2]

        pdf_url = self._extract_pdf_url(response)
        item["badge_pdf_url"] = pdf_url or ""
        item["file_urls"] = [pdf_url] if pdf_url else []

        if is_lab:
            item["badge_shop_url"] = response.xpath(
                "//a[.//span[contains(text(), 'Shop Now')]]/@href"
            ).get()
        else:
            item["badge_shop_url"] = self._extract_shop_url(response)

        # Get badge image URL
        if is_lab:
            image_url = self._extract_lab_image_url(response)
        else:
            image_url = self._extract_standard_image_url(response)
        item["badge_image_url"] = image_url or ""
        item["image_urls"] = [image_url] if image_url else []

        if is_lab:
            item["workbook_pdf_url"] = None
            item["workbook_docx_url"] = None
        else:
            # Helper to strict match
            # Try exact match first
            wb_data = self.workbook_links.get(item["badge_name"])

            if not wb_data:
                # Try caseless match and simple normalization (& -> and)
                target_lower = (
                    item["badge_name"].lower().replace("&", "and").replace("  ", " ")
                )
                for name, links in self.workbook_links.items():
                    name_lower = name.lower().replace("&", "and").replace("  ", " ")
                    if name_lower == target_lower:
                        wb_data = links
                        break

            if wb_data:
                item["workbook_pdf_url"] = wb_data.get("pdf")
                item["workbook_docx_url"] = wb_data.get("docx")
            else:
                self.logger.warning(
                    f"No workbook links found for badge: {item['badge_name']}"
                )
                item["workbook_pdf_url"] = None
                item["workbook_docx_url"] = None

        item["is_eagle_required"] = self._extract_is_eagle_required(response)

        if is_lab:
            lab_blocks = self._extract_lab_requirements_blocks(response)
            if not lab_blocks:
                self.logger.warning(
                    "No lab requirement content found for %s", response.url
                )
                semantic_requirements = []
            else:
                semantic_requirements = (
                    self._lab_requirements_extractor.extract_from_blocks(lab_blocks)
                )
        else:
            requirements_html = response.css("div.mb-requirement-container").get()
            if not requirements_html:
                requirements_html = response.text
            raw_requirements = self._requirements_extractor.extract(requirements_html)
            semantic_requirements = self._requirements_processor.process(
                raw_requirements
            )

        item["requirements_data"] = [
            requirement.model_dump() for requirement in semantic_requirements
        ]
        item["requirements_markdown"] = self._requirements_generator.generate(
            semantic_requirements
        )

        yield item

    def _extract_badge_name(self, response, is_lab=False):
        if is_lab:
            legacy_name = self._clean_badge_name(
                response.css("h1.elementor-heading-title::text").get()
            )
            if legacy_name:
                return legacy_name

        for title in (
            response.css("meta[property='og:title']::attr(content)").get(),
            response.css("title::text").get(),
        ):
            name = self._name_from_title(title)
            if name:
                return name

        heading_texts = self._elementor_heading_texts(response)
        for index, heading_text in enumerate(heading_texts):
            if heading_text.lower() == "merit badge" and index > 0:
                name = self._clean_badge_name(heading_texts[index - 1])
                if name:
                    return name

        return self._clean_badge_name(
            response.css("h1.elementor-heading-title::text").get()
        )

    def _extract_badge_overview(self, response):
        heading_xpath = (
            "//*[self::h2 or self::h3]"
            "[contains(translate(normalize-space(string(.)), "
            "'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), "
            "'MERIT BADGE OVERVIEW')]"
        )
        heading = response.xpath(heading_xpath)
        if heading:
            overview_text = (
                heading[0]
                .xpath(
                    "following::div[contains(@class, 'elementor-widget-text-editor')][1]"
                    "//div[contains(@class, 'elementor-widget-container')]//text()"
                )
                .getall()
            )
            overview = " ".join(text.strip() for text in overview_text if text.strip())
            if overview:
                return overview

        legacy_text = response.xpath(
            "//h3[contains(text(), 'Merit Badge Overview')]/../../following-sibling::div[1]"
            "//div[@class='elementor-widget-container']/text()"
        ).getall()
        return "".join(legacy_text).strip()

    def _extract_pdf_url(self, response):
        fallback_url = None
        for link in response.css("a[href]"):
            href = link.attrib.get("href", "")
            absolute = response.urljoin(href)
            text = self._normalize_space(link.xpath("string(.)").get())
            text_lower = text.lower()
            href_lower = absolute.lower()
            if (
                "download free pamphlet" in text_lower
                or "download the free pamphlet" in text_lower
            ):
                return absolute
            if (
                "filestore.scouting.org" in href_lower
                and "/pamphlets/" in href_lower
                and href_lower.endswith(".pdf")
            ):
                fallback_url = fallback_url or absolute
        return fallback_url

    def _extract_shop_url(self, response):
        shop_url = response.xpath(
            "//a[.//span[contains(text(), 'Shop Now')]]/@href"
        ).get()
        if shop_url:
            return response.urljoin(shop_url)

        pamphlet_shop_url = response.xpath(
            "//div[contains(@class, 'mb-scoutshop-pamphlet')]"
            "//a[contains(@href, 'scoutshop.org')]/@href"
        ).get()
        if pamphlet_shop_url:
            return response.urljoin(pamphlet_shop_url)

        for href in response.css("a[href*='scoutshop.org']::attr(href)").getall():
            href_lower = href.lower()
            if "merit-badge-pamphlet" in href_lower:
                return response.urljoin(href)
        return ""

    def _extract_is_eagle_required(self, response):
        overview_heading = response.xpath(
            "//*[contains(@class, 'elementor-heading-title')]"
            "[contains(translate(normalize-space(string(.)), "
            "'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), "
            "'MERIT BADGE OVERVIEW')]"
        )
        if overview_heading:
            header_text = " ".join(
                self._normalize_space(text)
                for text in overview_heading[0]
                .xpath(
                    "preceding::*[contains(@class, 'elementor-heading-title')]//text()"
                )
                .getall()
            )
            return "Eagle Required" in header_text

        header_text = " ".join(self._elementor_heading_texts(response)[:8])
        if header_text:
            return "Eagle Required" in header_text

        return bool(response.xpath("//h2[contains(text(), 'Eagle Required')]"))

    def _extract_standard_image_url(self, response):
        legacy_image = response.xpath(
            '//*[@id="page"]/div/section[1]/div/div/div/div[4]/div/div/div/section/div/div[2]/div/div/div/img/@src'
        ).get()
        if not self._is_placeholder_image_url(legacy_image):
            return response.urljoin(legacy_image)

        legacy_lazy_image = response.xpath(
            '//*[@id="page"]/div/section[1]/div/div/div/div[4]/div/div/div/section/div/div[2]/div/div/div/img/@data-src'
        ).get()
        if not self._is_placeholder_image_url(legacy_lazy_image):
            return response.urljoin(legacy_lazy_image)

        merit_badge_heading = response.xpath(
            "//*[contains(@class, 'elementor-heading-title')]"
            "[translate(normalize-space(string(.)), "
            "'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ') = 'MERIT BADGE']"
        )
        if merit_badge_heading:
            image_url = self._first_real_image_url(
                merit_badge_heading[0].xpath(
                    "./ancestor::div[contains(@class, 'e-con')][1]"
                    "/preceding-sibling::*[1]//img"
                ),
                response,
            )
            if image_url:
                return image_url

        overview_heading = response.xpath(
            "//*[contains(@class, 'elementor-heading-title')]"
            "[contains(translate(normalize-space(string(.)), "
            "'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), "
            "'MERIT BADGE OVERVIEW')]"
        )
        if overview_heading:
            image_url = self._first_real_image_url(
                overview_heading[0].xpath("preceding::img"), response
            )
            if image_url:
                return image_url

        return None

    def _first_real_image_url(self, images, response):
        for image in images:
            for attr in ("data-src", "src"):
                image_url = image.attrib.get(attr)
                if not self._is_placeholder_image_url(image_url):
                    return response.urljoin(image_url)
        return None

    def _is_placeholder_image_url(self, image_url):
        if not image_url:
            return True
        image_url_lower = image_url.lower()
        return (
            image_url_lower.startswith("data:")
            or "eagle_scout_logo" in image_url_lower
            or "eagle-scout-logo" in image_url_lower
            or "prepared-for-life-logo" in image_url_lower
            or "scouting-america-prepared" in image_url_lower
        )

    def _elementor_heading_texts(self, response):
        return [
            text
            for text in (
                self._normalize_space(heading.xpath("string(.)").get())
                for heading in response.css(".elementor-heading-title")
            )
            if text
        ]

    def _name_from_title(self, title):
        if not title:
            return ""
        normalized = self._normalize_space(title)
        normalized = normalized.split("|", 1)[0].strip()
        match = re.match(r"^(.+?)\s+Merit Badge$", normalized, flags=re.IGNORECASE)
        if match:
            return self._clean_badge_name(match.group(1))
        return ""

    def _clean_badge_name(self, name):
        if not name:
            return ""
        return self._normalize_space(name).replace("Merit Badge", "").strip()

    def _normalize_space(self, text):
        return " ".join(text.split()) if text else ""

    def _extract_lab_image_url(self, response):
        image_url = response.xpath(
            "//h1[contains(@class,'elementor-heading-title')]/ancestor::div[contains(@class,'elementor-widget-heading')][1]"
            "/preceding-sibling::div[contains(@class,'elementor-widget-image')][1]//img/@src"
        ).get()
        if not image_url or image_url.startswith("data:"):
            image_url = response.xpath(
                "//h1[contains(@class,'elementor-heading-title')]/ancestor::div[contains(@class,'elementor-widget-heading')][1]"
                "/preceding-sibling::div[contains(@class,'elementor-widget-image')][1]//img/@data-src"
            ).get()
        if image_url:
            return image_url
        image_url = response.xpath(
            "//h1[contains(@class,'elementor-heading-title')]/ancestor::div[contains(@class,'e-con')][1]"
            "//div[contains(@class,'elementor-widget-image')]//img/@src"
        ).get()
        if not image_url or image_url.startswith("data:"):
            image_url = response.xpath(
                "//h1[contains(@class,'elementor-heading-title')]/ancestor::div[contains(@class,'e-con')][1]"
                "//div[contains(@class,'elementor-widget-image')]//img/@data-src"
            ).get()
        return image_url

    def _extract_lab_requirements_blocks(self, response):
        heading_xpath = (
            "//*[self::h1 or self::h2 or self::h3 or self::h4 or self::h5 or self::h6]"
            "[contains(translate(normalize-space(string(.)), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'REQUIREMENTS')]"
        )
        heading = response.xpath(heading_xpath)
        if not heading:
            return []
        heading = heading[0]
        container = heading.xpath("./ancestor::div[contains(@class, 'e-con')][1]")
        widgets = []
        if container:
            widgets = container.xpath(
                ".//div[contains(@class, 'elementor-widget-text-editor')]"
            )
        if not widgets:
            widgets = heading.xpath(
                "./ancestor::div[contains(@class, 'elementor-widget')][1]/following-sibling::div[contains(@class, 'elementor-widget-text-editor')]"
            )
        blocks = []
        for widget in widgets:
            content = widget.css("div.elementor-widget-container").get()
            if content:
                blocks.append(content)
        return blocks

    def extract_sub_requirements(self, incoming_parent_id, selector):
        if len(selector) == 0:
            return []

        reqs = []
        for req_li in selector:
            req_internal_parent_id, req_internal_id = extract_parent_and_req_ids(req_li)
            if not req_internal_parent_id:
                req_internal_parent_id = incoming_parent_id

            # Get text with Markdown links
            req_li_text = extract_text_with_markdown_links(req_li)

            # Remove any nested ul content (sub-requirements) from the text
            nested_ul = req_li.css("ul")
            if nested_ul:
                nested_text = extract_text_with_markdown_links(nested_ul)
                if nested_text:
                    req_li_text = req_li_text.replace(nested_text, "").strip()

            req_id, req_text = extract_requirement_identifier(req_li_text)

            req = {
                "id": req_id,
                "text": clean_sub_requirement(req_text),
                "internal_parent_id": req_internal_parent_id,
                "internal_id": req_internal_id,
                "requirements": [],
            }
            reqs.append(req)

            # Check if sub_req_li has a child ul element
            sub_lis = req_li.css("ul > li")
            if len(sub_lis) > 0:
                sub_reqs = self.extract_sub_requirements(req_internal_id, sub_lis)
                reqs.extend(sub_reqs)
        return reqs


def extract_text_with_markdown_links(selector):
    """Extract text content and convert links to Markdown format and lists to Markdown lists"""
    # Get all text content first
    text_content = selector.xpath("string(.)").get() or ""

    # Replace links with Markdown format
    links = selector.css("a")
    for link in links:
        link_text = link.xpath("string(.)").get() or ""
        link_url = link.xpath("@href").get() or ""
        if link_text and link_url:
            text_content = text_content.replace(link_text, f"[{link_text}]({link_url})")

    # Convert HTML lists to Markdown lists
    lists = selector.css("ul, ol")
    for list_elem in lists:
        list_text = list_elem.xpath("string(.)").get() or ""
        if list_text:
            # Get list items
            items = list_elem.css("li")
            markdown_items = []
            for item in items:
                item_text = item.xpath("string(.)").get() or ""
                if item_text:
                    # Convert links in list items
                    item_links = item.css("a")
                    for link in item_links:
                        link_text = link.xpath("string(.)").get() or ""
                        link_url = link.xpath("@href").get() or ""
                        if link_text and link_url:
                            item_text = item_text.replace(
                                link_text, f"[{link_text}]({link_url})"
                            )
                    markdown_items.append(f"- {item_text.strip()}")

            if markdown_items:
                markdown_list = "\n" + "\n".join(markdown_items)
                text_content = text_content.replace(list_text, markdown_list)

    return text_content.strip()


def extract_parent_and_req_ids(selector):
    # Get the 'class' attribute as a string
    classes = selector.attrib.get("class", "")

    # Define regex patterns for parent and requirement IDs
    parent_pattern = re.compile(r"mb-parent-(\d+)")
    req_id_pattern = re.compile(r"mb-requirement-id-(\d+)")

    # Search for parent ID
    parent_match = parent_pattern.search(classes)
    parent_id = parent_match.group(1) if parent_match else None

    # Search for requirement ID
    req_id_match = req_id_pattern.search(classes)
    req_id = req_id_match.group(1) if req_id_match else None

    return parent_id, req_id


def extract_requirement_identifier(text):
    if not text:
        return None, None
    patterns = [
        r"^\s*\(?(\d+)[\.\)]\s*",  # Matches "2. ", "2) ", "(2) " etc.
        r"^\s*([A-Z])[.\)]\s*",  # Matches "A. ", "B) ", etc.
        r"^\s*\(([a-z])\)\s*",  # Matches "(a) ", "(b) ", etc.
    ]

    for pattern in patterns:
        match = re.match(pattern, text)
        if match:
            return match.group(1), match.string[match.end() :]
    return None, text


def clean_requirement_number(text):
    # If text is missing a trailing period, add it
    text = text.strip()
    if text == "":
        return None
    if not text.endswith("."):
        text += "."
    return text


def clean_requirement_text(text):
    return clean_text(text)


def clean_sub_requirement(text):
    return clean_text(text).replace("  ", " ")


def clean_text(text):
    return text.strip().replace("\r\n", " ").replace("\n", " ")
