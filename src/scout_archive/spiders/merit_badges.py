import scrapy
from scout_archive.items import MeritBadgeItem
import re


class MeritBadgesSpider(scrapy.Spider):
    name = "merit_badges"
    allowed_domains = ["scouting.org"]
    start_urls = ["https://www.scouting.org/skills/merit-badges/all/"]

    def __init__(self, name=None, url=None, **kwargs):
        self.single_url = url
        super().__init__(name, **kwargs)

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

            # Get the text of the requirement without the span.mb-requirement-listnumber
            parts = req.css(".mb-requirement-parent").xpath("text()").getall()
            req_text = clean_requirement_text("".join(p.strip() for p in parts))

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

            # Get the text within the li element without grabbing any <ul> elements that may be children
            # req_li_text = req_li.xpath("string(.)").get()
            req_li_text = " ".join(
                req_li.xpath("text() | .//strong/text() | .//em/text()").getall()
            ).strip()

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
