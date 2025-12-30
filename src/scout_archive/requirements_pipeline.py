from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Dict, List, Literal, Optional, Union

from bs4 import BeautifulSoup, NavigableString, Tag
from pydantic import BaseModel, Field, TypeAdapter


class RawTextNode(BaseModel):
    type: Literal["text"] = "text"
    value: str


class RawElementNode(BaseModel):
    type: Literal["element"] = "element"
    tag: str
    attrs: Dict[str, str] = Field(default_factory=dict)
    children: List["RawNode"] = Field(default_factory=list)


RawNode = Annotated[Union[RawTextNode, RawElementNode], Field(discriminator="type")]


class RawRequirementItem(BaseModel):
    id: str
    content_nodes: List[RawNode] = Field(default_factory=list)
    sub_requirements: List["RawRequirementItem"] = Field(default_factory=list)


class Resource(BaseModel):
    title: str
    url: str


class SemanticRequirement(BaseModel):
    id: str
    label: Optional[str] = None
    content: List[RawNode] = Field(default_factory=list)
    resources: List[Resource] = Field(default_factory=list)
    sub_requirements: List["SemanticRequirement"] = Field(default_factory=list)


RawElementNode.model_rebuild()
RawRequirementItem.model_rebuild()
SemanticRequirement.model_rebuild()


class HtmlExtractor:
    def __init__(self) -> None:
        self._adapter = TypeAdapter(List[RawRequirementItem])

    def extract(self, html: str) -> List[RawRequirementItem]:
        soup = BeautifulSoup(html, "html.parser")
        items = [
            self._parse_container(container)
            for container in soup.select("div.mb-requirement-item")
        ]
        return self._adapter.validate_python(items)

    def _parse_container(self, container: Tag) -> RawRequirementItem:
        parent = container.find("div", class_="mb-requirement-parent") or container
        requirement_id = self._extract_requirement_id(parent) or self._extract_requirement_id(
            container
        )
        content_nodes = self._convert_children(parent)
        sub_list = container.find("ul", class_="mb-requirement-children-list")
        sub_requirements = self._parse_children_list(sub_list)
        return RawRequirementItem(
            id=requirement_id or "",
            content_nodes=content_nodes,
            sub_requirements=sub_requirements,
        )

    def _parse_children_list(self, list_tag: Optional[Tag]) -> List[RawRequirementItem]:
        if not list_tag:
            return []
        children = []
        for child in list_tag.find_all("li", class_="mb-requirement-child", recursive=False):
            children.append(self._parse_child_item(child))
        return children

    def _parse_child_item(self, item_tag: Tag) -> RawRequirementItem:
        requirement_id = self._extract_requirement_id(item_tag) or ""
        content_nodes = self._convert_children(item_tag)
        sub_list = item_tag.find("ul", class_="mb-requirement-children-list")
        sub_requirements = self._parse_children_list(sub_list)
        return RawRequirementItem(
            id=requirement_id,
            content_nodes=content_nodes,
            sub_requirements=sub_requirements,
        )

    def _convert_children(self, parent: Tag) -> List[RawNode]:
        nodes: List[RawNode] = []
        for child in parent.contents:
            if isinstance(child, NavigableString):
                text = str(child)
                nodes.append(RawTextNode(value=text))
                continue

            if isinstance(child, Tag):
                if self._is_children_list(child):
                    continue
                node = self._convert_tag(child)
                if node is not None:
                    nodes.append(node)
        return nodes

    def _convert_tag(self, tag: Tag) -> Optional[RawElementNode]:
        attrs = self._normalize_attrs(tag.attrs)
        children = []
        for child in tag.contents:
            if isinstance(child, NavigableString):
                text = str(child)
                children.append(RawTextNode(value=text))
            elif isinstance(child, Tag):
                if self._is_children_list(child):
                    continue
                child_node = self._convert_tag(child)
                if child_node is not None:
                    children.append(child_node)
        return RawElementNode(tag=tag.name, attrs=attrs, children=children)

    def _normalize_attrs(self, attrs: Dict[str, object]) -> Dict[str, str]:
        normalized: Dict[str, str] = {}
        for key, value in attrs.items():
            if value is None:
                continue
            if isinstance(value, list):
                normalized[key] = " ".join(str(part) for part in value)
            else:
                normalized[key] = str(value)
        return normalized

    def _extract_requirement_id(self, tag: Tag) -> Optional[str]:
        for class_name in tag.get("class", []):
            match = re.match(r"mb-requirement-id-(\d+)", class_name)
            if match:
                return match.group(1)
        return None

    def _is_children_list(self, tag: Tag) -> bool:
        return "mb-requirement-children-list" in (tag.get("class") or [])


class SemanticProcessor:
    RESOURCE_LABEL_RE = re.compile(r"^\s*resources?:\s*$", re.IGNORECASE)
    INLINE_SPACE_TAGS = {"a", "b", "em", "i", "strong"}
    TEXT_LABEL_RE = re.compile(r"^\s*(\([A-Za-z0-9]+\)|[A-Za-z0-9]+[.)]+)\s*")
    EXCLUDED_NOTE_RE = re.compile(
        r"\bthe official merit badge pamphlets are now free and downloadable\b",
        re.IGNORECASE,
    )

    def process(self, raw_items: List[RawRequirementItem]) -> List[SemanticRequirement]:
        processed: List[SemanticRequirement] = []
        for item in raw_items:
            if self._is_excluded_requirement(item):
                continue
            processed.append(self._process_item(item))
        return processed

    def _process_item(self, item: RawRequirementItem) -> SemanticRequirement:
        label, content_nodes = self._promote_label(item.content_nodes)
        resources: List[Resource] = []
        content_nodes = self._extract_resources(content_nodes, resources)
        content_nodes = self._normalize_text(content_nodes)
        content_nodes = self._clean_attributes(content_nodes)
        sub_requirements = [
            self._process_item(sub)
            for sub in item.sub_requirements
            if not self._is_excluded_requirement(sub)
        ]
        return SemanticRequirement(
            id=item.id,
            label=label,
            content=content_nodes,
            resources=resources,
            sub_requirements=sub_requirements,
        )

    def _is_excluded_requirement(self, item: RawRequirementItem) -> bool:
        text = self._nodes_text(item.content_nodes)
        if not text:
            return False
        normalized = re.sub(r"\s+", " ", text).strip()
        return bool(self.EXCLUDED_NOTE_RE.search(normalized))

    def _promote_label(self, nodes: List[RawNode]) -> tuple[Optional[str], List[RawNode]]:
        label = None
        cleaned: List[RawNode] = []
        for node in nodes:
            if isinstance(node, RawElementNode) and node.tag == "span":
                class_attr = node.attrs.get("class", "")
                if "mb-requirement-listnumber" in class_attr:
                    label = self._normalize_label(self._node_text(node))
                    continue
            cleaned.append(node)
        if label:
            return label, cleaned

        if cleaned:
            first = cleaned[0]
            if isinstance(first, RawTextNode):
                match = self.TEXT_LABEL_RE.match(first.value)
                if match:
                    label = self._normalize_label(match.group(1))
                    remainder = first.value[match.end() :]
                    if remainder:
                        cleaned[0] = RawTextNode(value=remainder)
                    else:
                        cleaned = cleaned[1:]
        return label, cleaned

    def _normalize_label(self, label: str) -> Optional[str]:
        cleaned = label.strip()
        if not cleaned:
            return None
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = cleaned[1:-1]
        cleaned = cleaned.lstrip("(").rstrip(")")
        cleaned = cleaned.rstrip(".")
        cleaned = cleaned.strip()
        return cleaned or None

    def _extract_resources(
        self, nodes: List[RawNode], resources: List[Resource]
    ) -> List[RawNode]:
        if not self._has_resource_label(nodes):
            return nodes

        cleaned: List[RawNode] = []
        skip_next_break = False
        for node in nodes:
            updated_node, removed = self._extract_resources_from_node(node, resources)
            if removed:
                if cleaned and self._is_break(cleaned[-1]):
                    cleaned.pop()
                skip_next_break = True
                continue
            if updated_node is None:
                continue
            if skip_next_break and self._is_break(updated_node):
                continue
            skip_next_break = False
            cleaned.append(updated_node)
        return cleaned

    def _has_resource_label(self, nodes: List[RawNode]) -> bool:
        for node in nodes:
            if isinstance(node, RawTextNode):
                if self.RESOURCE_LABEL_RE.match(node.value.strip()):
                    return True
            elif isinstance(node, RawElementNode):
                if node.tag in {"i", "em"} and self.RESOURCE_LABEL_RE.match(
                    self._node_text(node).strip()
                ):
                    return True
                if self._has_resource_label(node.children):
                    return True
        return False

    def _extract_resources_from_node(
        self, node: RawNode, resources: List[Resource]
    ) -> tuple[Optional[RawNode], bool]:
        if isinstance(node, RawTextNode):
            if self.RESOURCE_LABEL_RE.match(node.value.strip()):
                return None, True
            return node, False

        if isinstance(node, RawElementNode):
            if node.tag == "a":
                title = self._node_text(node).strip()
                url = node.attrs.get("href", "")
                if title and url:
                    resources.append(Resource(title=title, url=url))
                return None, True

            if node.tag in {"i", "em"}:
                if self.RESOURCE_LABEL_RE.match(self._node_text(node).strip()):
                    return None, True

            cleaned_children = self._extract_resources(node.children, resources)
            return (
                RawElementNode(tag=node.tag, attrs=node.attrs, children=cleaned_children),
                False,
            )

        return None, False

    def _normalize_text(self, nodes: List[RawNode]) -> List[RawNode]:
        normalized: List[RawNode] = []
        for node in nodes:
            if isinstance(node, RawTextNode):
                value = node.value.replace("\xa0", " ")
                value = re.sub(r"\s+", " ", value)
                if normalized and isinstance(normalized[-1], RawTextNode):
                    combined = normalized[-1].value + value
                    combined = re.sub(r"\s+", " ", combined)
                    normalized[-1] = RawTextNode(value=combined)
                else:
                    normalized.append(RawTextNode(value=value))
                continue

            if isinstance(node, RawElementNode):
                children = self._normalize_text(node.children)
                normalized.append(
                    RawElementNode(tag=node.tag, attrs=node.attrs, children=children)
                )

        normalized = self._trim_edge_whitespace(normalized)
        normalized = self._ensure_inline_spacing(normalized)
        return normalized

    def _trim_edge_whitespace(self, nodes: List[RawNode]) -> List[RawNode]:
        while nodes and isinstance(nodes[0], RawTextNode):
            stripped = nodes[0].value.lstrip()
            if stripped == "":
                nodes.pop(0)
            else:
                nodes[0] = RawTextNode(value=stripped)
                break

        while nodes and isinstance(nodes[-1], RawTextNode):
            stripped = nodes[-1].value.rstrip()
            if stripped == "":
                nodes.pop()
            else:
                nodes[-1] = RawTextNode(value=stripped)
                break

        return nodes

    def _ensure_inline_spacing(self, nodes: List[RawNode]) -> List[RawNode]:
        for index in range(len(nodes) - 1):
            current = nodes[index]
            next_node = nodes[index + 1]
            if (
                isinstance(current, RawElementNode)
                and current.tag in self.INLINE_SPACE_TAGS
                and isinstance(next_node, RawTextNode)
            ):
                next_value = next_node.value
                if not next_value:
                    continue
                if next_value[0].isspace() or next_value[0] in ".,;:?!)]":
                    continue
                if self._node_text(current).endswith(" "):
                    continue
                nodes[index + 1] = RawTextNode(value=f" {next_value}")
        return nodes

    def _clean_attributes(self, nodes: List[RawNode]) -> List[RawNode]:
        cleaned: List[RawNode] = []
        for node in nodes:
            if isinstance(node, RawTextNode):
                cleaned.append(node)
                continue

            if isinstance(node, RawElementNode):
                children = self._clean_attributes(node.children)
                attrs = {}
                if "href" in node.attrs:
                    attrs["href"] = node.attrs["href"]

                if node.tag not in {"b", "strong", "i", "em", "br", "a"}:
                    cleaned.extend(children)
                    continue

                cleaned.append(
                    RawElementNode(tag=node.tag, attrs=attrs, children=children)
                )

        return cleaned

    def _is_break(self, node: RawNode) -> bool:
        return isinstance(node, RawElementNode) and node.tag == "br"

    def _node_text(self, node: RawNode) -> str:
        if isinstance(node, RawTextNode):
            return node.value
        return "".join(self._node_text(child) for child in node.children)

    def _nodes_text(self, nodes: List[RawNode]) -> str:
        return "".join(self._node_text(node) for node in nodes)


class MarkdownGenerator:
    def generate(self, requirements: List[SemanticRequirement]) -> str:
        lines: List[str] = []
        for index, requirement in enumerate(requirements):
            if index > 0:
                lines.append("")
            lines.extend(self._render_requirement(requirement, level=0))
        return "\n".join(line.rstrip() for line in lines).rstrip()

    def _render_requirement(
        self, requirement: SemanticRequirement, level: int
    ) -> List[str]:
        indent = "  " * level
        label = requirement.label.strip() if requirement.label else None
        marker = "-"
        content = self._render_nodes(requirement.content).strip()
        content = re.sub(r"\n[ \t]+", "\n", content)
        if label:
            content = f"{self._format_label(label)} {content}".strip()

        prefix = f"{indent}{marker} "
        lines: List[str] = []
        if content:
            content_lines = content.splitlines()
            lines.append(prefix + content_lines[0])
            continuation_indent = indent + " " * (len(marker) + 1)
            for line in content_lines[1:]:
                lines.append(continuation_indent + line)
        else:
            lines.append(prefix.rstrip())
            continuation_indent = indent + " " * (len(marker) + 1)

        if requirement.resources:
            lines.append("")
            resources_text = ", ".join(
                f"[{resource.title}]({resource.url})"
                for resource in requirement.resources
            )
            lines.append(continuation_indent + f"**Resources:** {resources_text}")
            if requirement.sub_requirements:
                lines.append("")

        for child in requirement.sub_requirements:
            lines.extend(self._render_requirement(child, level + 1))

        return lines

    def _format_label(self, label: str) -> str:
        cleaned = label.strip()
        if not cleaned:
            return ""
        return f"({cleaned})"

    def _render_nodes(self, nodes: List[RawNode]) -> str:
        parts: List[str] = []
        for node in nodes:
            if isinstance(node, RawTextNode):
                parts.append(node.value)
                continue

            if isinstance(node, RawElementNode):
                inner = self._render_nodes(node.children)
                if node.tag in {"b", "strong"}:
                    parts.append(f"**{inner}**")
                elif node.tag in {"i", "em"}:
                    parts.append(f"*{inner}*")
                elif node.tag == "a":
                    href = node.attrs.get("href", "").strip()
                    if href:
                        parts.append(f"[{inner}]({href})")
                    else:
                        parts.append(inner)
                elif node.tag == "br":
                    parts.append("\n")
                else:
                    parts.append(inner)
        return "".join(parts)


if __name__ == "__main__":
    SAMPLE_HTML = """
    <div class="mb-requirement-container">
      <div class="mb-requirement-item">
        <div class="mb-requirement-parent mb-requirement-id-100">
          <span class="mb-requirement-listnumber">1.</span>
          Explain the purpose of space exploration.<br>
          <i>Resources:</i>
          <a href="https://example.com/overview">Overview Article</a>
        </div>
        <ul class="mb-requirement-children-list">
          <li class="mb-requirement-child mb-parent-100 mb-requirement-id-101">(a)
            Describe historical reasons.</li>
        </ul>
      </div>
    </div>
    """

    extractor = HtmlExtractor()
    raw_items = extractor.extract(SAMPLE_HTML)
    adapter = TypeAdapter(List[RawRequirementItem])
    raw_json = adapter.dump_json(raw_items, indent=2)
    Path("raw_tree.json").write_bytes(raw_json)

    loaded_raw = adapter.validate_json(raw_json)
    processor = SemanticProcessor()
    semantic_items = processor.process(loaded_raw)
    markdown = MarkdownGenerator().generate(semantic_items)
    print(markdown)
