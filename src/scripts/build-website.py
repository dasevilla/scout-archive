#!/usr/bin/env python3
"""Build website with proper directory structure."""

import shutil
from pathlib import Path


def build_website():
    """Build website with merit badges and cub adventures in subdirs."""
    site_dir = Path("_site")
    build_dir = Path("build")

    # Clean and create site directory
    if site_dir.exists():
        shutil.rmtree(site_dir)
    site_dir.mkdir()

    # Copy merit badges to subdirectory
    mb_source = build_dir / "merit-badges"
    mb_dest = site_dir / "merit-badges"
    if mb_source.exists():
        shutil.copytree(mb_source, mb_dest)

    # Copy cub adventures to subdirectory
    ca_source = build_dir / "cub-scout-adventures"
    ca_dest = site_dir / "cub-scout-adventures"
    if ca_source.exists():
        shutil.copytree(ca_source, ca_dest)

    # Create root index
    index_content = """# Scout Requirements Archive

An unofficial automated archive of Scouting America requirements.

## Contents

- [Merit Badges](merit-badges/)
- [Cub Scout Adventures](cub-scout-adventures/)

**Last updated:** {date}
""".format(date=__import__("datetime").datetime.now().strftime("%Y-%m-%d"))

    (site_dir / "index.md").write_text(index_content)

    # Create Jekyll config
    config_content = """theme: jekyll-theme-cayman
title: Scout Requirements Archive
description: Unofficial archive of Scouting America requirements
"""
    (site_dir / "_config.yml").write_text(config_content)


if __name__ == "__main__":
    build_website()
