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
    # An image of the badge
    badge_image_url = scrapy.Field()
    # True if the badge is Eagle-required
    is_eagle_required = scrapy.Field()

    # Requirements in a structured data format
    requirements_data = scrapy.Field()

    file_urls = scrapy.Field()
    files = scrapy.Field()

    image_urls = scrapy.Field()
    images = scrapy.Field()


class CubScoutAdventureItem(scrapy.Item):
    # Name of the rank
    rank_name = scrapy.Field()
    # Name of the adventure
    adventure_name = scrapy.Field()

    # Requirements in HTML format
    requirements_html = scrapy.Field()
    # Full HTML of the page
    requirements_md = scrapy.Field()
    # Requirements in a structured data format
    page_html = scrapy.Field()
