import scrapy
from scout_archive.items import MeritBadgeItem
import re


class MeritBadgesSpider(scrapy.Spider):
    name = "merit_badges"
    allowed_domains = ["scouting.org", "usscouts.org"]
    start_urls = ["https://www.scouting.org/skills/merit-badges/all/"]

    def __init__(self, name=None, url=None, **kwargs):
        self.single_url = url
        self.workbook_links = {}
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
            yield scrapy.Request(self.single_url, callback=self.parse_merit_badge)
        else:
            for url in self.start_urls:
                yield scrapy.Request(url, callback=self.parse_start_url_custom)

    def parse_start_url_custom(self, response):
        yield from response.follow_all(
            css="h2 a[href*='/merit-badges/']", callback=self.parse_merit_badge
        )

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
            yield scrapy.Request(self.single_url, callback=self.parse_merit_badge)
        else:
            # Grab every merit badge URL
            yield from response.follow_all(
                css="h2 a[href*='/merit-badges/']", callback=self.parse_merit_badge
            )

    def parse_merit_badge(self, response):
        item = MeritBadgeItem()

        # Get badge name
        badge_name_raw = response.css("h1.elementor-heading-title::text").get()
        item["badge_name"] = (
            badge_name_raw.replace("Merit Badge", "").strip() if badge_name_raw else ""
        )

        # Get badge overview
        # Extract the text content of the badge overview section
        # The xpath locates the h3 element containing 'Merit Badge Overview',
        # then navigates to its following sibling div, and extracts the text from
        # the div with class 'elementor-widget-container' :-(
        overview_text = response.xpath(
            "//h3[contains(text(), 'Merit Badge Overview')]/../../following-sibling::div[1]//div[@class='elementor-widget-container']/text()"
        ).getall()
        item["badge_overview"] = "".join(overview_text).strip()

        # Get badge URL
        item["badge_url"] = response.url

        # Get badge URL slug
        item["badge_url_slug"] = response.url.split("/")[-2]

        # Get badge PDF URL
        pdf_url = response.xpath(
            "//a[.//span[contains(text(), 'Download the Free Pamphlet')]]/@href"
        ).get()
        item["badge_pdf_url"] = pdf_url or ""
        item["file_urls"] = [pdf_url] if pdf_url else []

        # Get badge shop URL
        item["badge_shop_url"] = response.xpath(
            "//a[.//span[contains(text(), 'Shop Now')]]/@href"
        ).get()

        # Get badge image URL
        image_url = response.xpath(
            '//*[@id="page"]/div/section[1]/div/div/div/div[4]/div/div/div/section/div/div[2]/div/div/div/img/@src'
        ).get()
        # if image_url is an svg or None, use the data-src attribute instead
        if not image_url or image_url.startswith("data:"):
            image_url = response.xpath(
                '//*[@id="page"]/div/section[1]/div/div/div/div[4]/div/div/div/section/div/div[2]/div/div/div/img/@data-src'
            ).get()
        item["badge_image_url"] = image_url or ""
        item["image_urls"] = [image_url] if image_url else []

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

        # Check if the badge is Eagle-required by looking for "Eagle Required" in a <h2> element
        item["is_eagle_required"] = bool(
            response.xpath("//h2[contains(text(), 'Eagle Required')]")
        )

        # Extract requirements into a data structure
        requirements_list = []
        for req in response.css("div.mb-requirement-item"):
            # Get the internal parent and requirement IDs
            req_internal_parent_id, req_internal_id = extract_parent_and_req_ids(
                req.css(".mb-requirement-parent")
            )

            req_number, _ = extract_requirement_identifier(
                clean_requirement_number(
                    req.css("span.mb-requirement-listnumber::text").get()
                )
            )

            # Get the text content with links converted to Markdown
            req_text_element = req.css(".mb-requirement-parent")
            if req_text_element:
                req_text = extract_text_with_markdown_links(req_text_element)
                # Remove the requirement number from the beginning
                req_number_text = (
                    req.css("span.mb-requirement-listnumber::text").get() or ""
                )
                if req_number_text.strip():
                    req_text = req_text.replace(req_number_text.strip(), "", 1)
                req_text = clean_requirement_text(req_text)
            else:
                req_text = ""

            # Get the sub-requirements
            sub_reqs = self.extract_sub_requirements(
                req_internal_id, req.css("ul.mb-requirement-children-list > li")
            )
            requirements_list.extend(sub_reqs)

            requirements_list.append(
                {
                    "id": req_number,
                    "text": req_text,
                    "internal_parent_id": req_internal_parent_id,
                    "internal_id": req_internal_id,
                    "requirements": [],
                }
            )

        # Build the tree using internal IDs
        # Create a mapping from internal_id to requirement
        req_dict = {
            req["internal_id"]: req for req in requirements_list if req["internal_id"]
        }

        # List to hold root-level requirements
        root_requirements = []

        for req in requirements_list:
            parent_id = req["internal_parent_id"]
            if parent_id and parent_id in req_dict:
                # Attach to parent
                parent_req = req_dict[parent_id]
                parent_req["requirements"].append(req)
            else:
                # No parent found; this is a root requirement
                root_requirements.append(req)

        item["requirements_data"] = root_requirements

        yield item

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
