# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
import os
from pathlib import Path
import re
import json
import logging
import mimetypes

from jinja2 import Environment, FileSystemLoader
from scrapy.pipelines.files import FilesPipeline
from scrapy.pipelines.images import ImagesPipeline

from scout_archive.items import MeritBadgeItem, CubScoutAdventureItem

logger = logging.getLogger("scout_archive.pipelines")


class MeritBadgeFilesPipeline(FilesPipeline):
    def file_path(self, request, response=None, info=None, *, item=None):
        media_guid = sanitize_filename(item["badge_url_slug"]) + "-merit-badge"
        media_ext = Path(request.url).suffix
        # Handles empty and wild extensions by trying to guess the
        # mime type then extension or default to empty string otherwise
        if media_ext not in mimetypes.types_map:
            media_ext = ""
            media_type = mimetypes.guess_type(request.url)[0]
            if media_type:
                media_ext = mimetypes.guess_extension(media_type)
        return f"{media_guid}{media_ext}"


class MeritBadgeImagesPipeline(ImagesPipeline):
    def file_path(self, request, response=None, info=None, *, item=None):
        image_guid = sanitize_filename(item["badge_url_slug"]) + "-merit-badge"
        filename = f"{image_guid}.jpg"
        # Store the local filename in the item
        item["badge_image_filename"] = filename
        return filename


class CubScoutAdventureImagesPipeline(ImagesPipeline):
    def file_path(self, request, response=None, info=None, *, item=None):
        rank_name = sanitize_filename(item["rank_name"])
        adventure_name = sanitize_filename(item["adventure_name"])
        filename = f"{rank_name}/images/{adventure_name}.jpg"
        # Store the local filename in the item
        item["adventure_image_filename"] = filename
        return filename


class ScoutArchivePipeline:
    def __init__(self, merit_badge_output_dir, cub_adventure_output_dir):
        self.merit_badge_output_dir = merit_badge_output_dir
        self.cub_scout_adventure_output_dir = cub_adventure_output_dir
        # Initialize the Jinja2 environment
        template_dir = os.path.join(os.path.dirname(__file__), "templates")
        # print(f"Using TEMPLATE_DIR: {template_dir}")  # For debugging
        logger.debug(f"Using TEMPLATE_DIR: {template_dir}")
        self.env = Environment(
            loader=FileSystemLoader(template_dir), trim_blocks=True, lstrip_blocks=True
        )

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            merit_badge_output_dir=crawler.settings.get("MERIT_BADGE_OUTPUT_DIR"),
            cub_adventure_output_dir=crawler.settings.get("CUB_ADVENTURE_OUTPUT_DIR"),
        )

    def process_item(self, item, spider):
        if isinstance(item, MeritBadgeItem):
            self.process_merit_badge_item(item)
        elif isinstance(item, CubScoutAdventureItem):
            self.process_cub_scout_adventure_item(item)
        return item

    def process_merit_badge_item(self, item):
        filename_base = sanitize_filename(item["badge_url_slug"]) + "-merit-badge"
        output_dir = self.merit_badge_output_dir
        os.makedirs(output_dir, exist_ok=True)

        # Save merit badge as JSON
        json_filename = os.path.join(output_dir, f"{filename_base}.json")
        with open(json_filename, "w", encoding="utf-8") as f:
            payload = {
                "name": item.get("badge_name"),
                "overview": item.get("badge_overview"),
                "is_eagle_required": item.get("is_eagle_required"),
                "url": item.get("badge_url"),
                "pdf_url": item.get("badge_pdf_url"),
                "shop_url": item.get("badge_shop_url"),
                "image_url": item.get("badge_image_url"),
                "image_filename": item.get("badge_image_filename"),
                "requirements": item.get("requirements_data"),
            }
            json.dump(payload, f, ensure_ascii=False, indent=2)

        # Render and save Markdown file using Jinja2
        md_filename = os.path.join(output_dir, f"{filename_base}.md")
        template = self.env.get_template("merit_badge_template.md")
        markdown_content = template.render(**item)
        with open(md_filename, "w", encoding="utf-8") as f:
            f.write(markdown_content)

    def process_cub_scout_adventure_item(self, item):
        rank_name = item["rank_name"]
        adventure_name = item["adventure_name"]
        filename_base = sanitize_filename(adventure_name)
        output_dir = os.path.join(
            self.cub_scout_adventure_output_dir, sanitize_filename(rank_name)
        )
        os.makedirs(output_dir, exist_ok=True)

        # Save adventure as JSON
        json_filename = os.path.join(output_dir, f"{filename_base}.json")
        with open(json_filename, "w", encoding="utf-8") as f:
            payload = {
                "rank_name": item.get("rank_name"),
                "adventure_name": item.get("adventure_name"),
                "adventure_type": item.get("adventure_type"),
                "adventure_category": item.get("adventure_category"),
                "adventure_overview": item.get("adventure_overview"),
                "url": item.get("adventure_url"),
                "image_url": item.get("adventure_image_url"),
                "image_filename": item.get("adventure_image_filename"),
                "requirements": item.get("requirements_data"),
            }
            json.dump(payload, f, ensure_ascii=False, indent=2)

        # Render and save Markdown file using Jinja2
        md_filename = os.path.join(output_dir, f"{filename_base}.md")
        template = self.env.get_template("cub_scout_adventure_template.md")
        payload = {
            "rank_name": item.get("rank_name"),
            "adventure_name": item.get("adventure_name"),
            "adventure_type": item.get("adventure_type"),
            "adventure_category": item.get("adventure_category"),
            "adventure_overview": item.get("adventure_overview"),
            "adventure_url": item.get("adventure_url"),
            "adventure_image_url": item.get("adventure_image_url"),
            "adventure_image_filename": item.get("adventure_image_filename"),
            "requirements_data": item.get("requirements_data", []),
        }
        markdown_content = template.render(**payload)
        with open(md_filename, "w", encoding="utf-8") as f:
            f.write(markdown_content)


def sanitize_filename(name):
    # Replace spaces with dashes
    name = name.replace(" ", "-").lower()
    # Remove invalid characters
    return re.sub(r'[\\/*?:"<>|,]', "", name)
