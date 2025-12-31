import os
import json
import sys
from datetime import datetime


def generate_index(directory, index_filename="index.md"):
    """
    Generates an index Markdown file listing all Markdown files in a directory.

    Parameters:
        directory (str): The path to the directory.
        index_filename (str): The name of the index file to create.
    """
    # Get all JSON files in the directory
    json_files = [
        f
        for f in os.listdir(directory)
        if f.endswith(".json") and os.path.isfile(os.path.join(directory, f))
    ]
    json_files.sort()  # Sort files by name

    index_lines = [
        "# List of Scouts BSA Merit Badges",
        "",
        "This is an unofficial archive of [Scouts BSA Merit Badges](https://www.scouting.org/skills/merit-badges/all/) that was automatically extracted from the Scouting America website and may contain errors. Merit Badge requirements are also available as JSON files.",
        "",
    ]

    eagle_required_lines = ["## Eagle required Merit Badges", ""]

    all_badges_lines = ["## All Merit Badges", ""]

    for filename in json_files:
        filepath = os.path.join(directory, filename)
        with open(filepath, "r", encoding="utf-8") as file:
            data = json.load(file)
            name = data.get("name", "Unknown")
            url = data.get("url", "#")
            pdf_url = data.get("pdf_url", "")
            is_eagle_required = data.get("is_eagle_required", False)
            eagle_required_text = " 🦅" if is_eagle_required else ""
            md_filename = filename.replace(".json", ".md")
            link = f"[{name}]({md_filename})"
            line_parts = [f"1. {link}", f"[Original]({url})"]
            if pdf_url:
                line_parts.append(f"[PDF]({pdf_url})")
            line = " - ".join(line_parts)
            all_badges_lines.append(line + eagle_required_text)
            if is_eagle_required:
                eagle_required_lines.append(line)

    # Combine all lines
    index_lines.extend(eagle_required_lines)
    index_lines.append("")
    index_lines.extend(all_badges_lines)

    # Add footer
    index_lines.append("")
    generated_date = datetime.now().strftime("%Y-%m-%d")
    index_lines.append(
        f"Generated on {generated_date} by [Scouts BSA Merit Badge Archive](https://github.com/dasevilla)"
    )

    # Write the index file
    index_content = "\n".join(index_lines)
    index_path = os.path.join(directory, index_filename)
    with open(index_path, "w", encoding="utf-8") as index_file:
        index_file.write(index_content)
    print(f"Index file generated at {index_path}")


if __name__ == "__main__":
    # Accept directory path from command-line arguments or use current directory
    directory = sys.argv[1] if len(sys.argv) > 1 else "."
    generate_index(directory)
