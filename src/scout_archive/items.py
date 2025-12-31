# Define here the models for your archived items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class MeritBadgeItem(scrapy.Item):
    # Name of the merit badge
    badge_name = scrapy.Field()
    # URL to the badge overview page
    badge_overview = scrapy.Field()
    # URL slug for the badge
    badge_url_slug = scrapy.Field()
    # URL to the homepage
    badge_url = scrapy.Field()
    # URL to download the requirements PDF
    badge_pdf_url = scrapy.Field()
    # URL to buy the pamphlet
    badge_shop_url = scrapy.Field()
    # URL to the workbook PDF
    workbook_pdf_url = scrapy.Field()
    # URL to the workbook DOCX
    workbook_docx_url = scrapy.Field()
    # An image of the badge
    badge_image_url = scrapy.Field()
    # Local filename of the downloaded badge image
    badge_image_filename = scrapy.Field()
    # True if the badge is Eagle-required
    is_eagle_required = scrapy.Field()
    # True if the badge is a Merit Badge Lab badge
    is_lab = scrapy.Field()

    # Requirements in a structured data format
    requirements_data = scrapy.Field()
    # Requirements rendered as Markdown via the extraction pipeline
    requirements_markdown = scrapy.Field()

    file_urls = scrapy.Field()
    files = scrapy.Field()

    image_urls = scrapy.Field()
    images = scrapy.Field()


class CubScoutAdventureItem(scrapy.Item):
    # Name of the rank
    rank_name = scrapy.Field()
    # Name of the adventure
    adventure_name = scrapy.Field()
    # URL slug for the adventure
    adventure_url_slug = scrapy.Field()
    # URL to the adventure page
    adventure_url = scrapy.Field()
    # Adventure type (required/elective/special)
    adventure_type = scrapy.Field()
    # Adventure category (e.g., Personal Fitness, Character & Leadership)
    adventure_category = scrapy.Field()
    # Adventure overview/description
    adventure_overview = scrapy.Field()
    # An image of the adventure
    adventure_image_url = scrapy.Field()
    # Local filename of the downloaded adventure image
    adventure_image_filename = scrapy.Field()

    # Requirements in a structured data format
    requirements_data = scrapy.Field()

    image_urls = scrapy.Field()
    images = scrapy.Field()
