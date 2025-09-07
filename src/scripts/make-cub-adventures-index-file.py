import os
import json
import sys
from datetime import datetime


def generate_index(directory, index_filename="index.md"):
    """
    Generates an index Markdown file listing all Cub Scout adventures.

    Parameters:
        directory (str): The path to the directory.
        index_filename (str): The name of the index file to create.
    """
    # Get all JSON files in subdirectories (organized by rank)
    json_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".json"):
                json_files.append(os.path.join(root, file))

    json_files.sort()  # Sort files by name

    index_lines = [
        "# List of Cub Scout Adventures",
        "",
        "This is an unofficial archive of [Cub Scout Adventures](https://www.scouting.org/programs/cub-scouts/adventures/) that was automatically extracted from the Scouting America website and may contain errors. Adventure requirements are also available as JSON files.",
        "",
    ]

    # Group adventures by rank
    adventures_by_rank = {}

    for filepath in json_files:
        try:
            with open(filepath, "r", encoding="utf-8") as file:
                data = json.load(file)
                rank_name = data.get("rank_name", "Unknown")
                adventure_name = data.get("adventure_name", "Unknown")
                adventure_url = data.get("url", "#")
                adventure_type = data.get("adventure_type", "")

                # Get relative path for markdown file
                rel_path = os.path.relpath(filepath, directory)
                md_filename = rel_path.replace(".json", ".md")

                if rank_name not in adventures_by_rank:
                    adventures_by_rank[rank_name] = []

                adventures_by_rank[rank_name].append(
                    {
                        "name": adventure_name,
                        "url": adventure_url,
                        "type": adventure_type,
                        "md_file": md_filename,
                    }
                )
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Error reading {filepath}: {e}")
            continue

    # Generate sections for each rank
    rank_order = ["Lion", "Tiger", "Wolf", "Bear", "Webelos", "Arrow of Light"]

    for rank in rank_order:
        if rank in adventures_by_rank:
            index_lines.append(f"## {rank} Adventures")
            index_lines.append("")

            # Sort adventures by type (Required first, then Elective)
            adventures = adventures_by_rank[rank]
            adventures.sort(key=lambda x: (x["type"] != "Required", x["name"]))

            for adventure in adventures:
                type_indicator = (
                    " (Required)" if "Required" in adventure["type"] else ""
                )
                link = f"[{adventure['name']}]({adventure['md_file']})"
                line = f"1. {link} - [Original]({adventure['url']}){type_indicator}"
                index_lines.append(line)

            index_lines.append("")

    # Add footer
    generated_date = datetime.now().strftime("%Y-%m-%d")
    index_lines.append(
        f"Generated on {generated_date} by [Scout Archive](https://github.com/dasevilla/scout-archive)"
    )

    # Write the index file
    index_content = "\n".join(index_lines)
    index_path = os.path.join(directory, index_filename)
    with open(index_path, "w", encoding="utf-8") as index_file:
        index_file.write(index_content)
    print(f"Cub Adventures index file generated at {index_path}")


if __name__ == "__main__":
    # Accept directory path from command-line arguments or use current directory
    directory = sys.argv[1] if len(sys.argv) > 1 else "."
    generate_index(directory)
