from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Callable, Dict, List, Literal, Optional, Union

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

    def extract_nodes(self, html: str) -> List[RawNode]:
        soup = BeautifulSoup(html, "html.parser")
        root = soup.body if soup.body else soup
        return self._convert_children(root)

    def _parse_container(self, container: Tag) -> RawRequirementItem:
        parent = container.find("div", class_="mb-requirement-parent") or container
        requirement_id = self._extract_requirement_id(
            parent
        ) or self._extract_requirement_id(container)
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
        for child in list_tag.find_all(
            "li", class_="mb-requirement-child", recursive=False
        ):
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
    RESOURCE_LABEL_TAGS = {"b", "em", "i", "span", "strong"}
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

    def _promote_label(
        self, nodes: List[RawNode]
    ) -> tuple[Optional[str], List[RawNode]]:
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
            if isinstance(first, RawElementNode) and first.tag in {"b", "strong"}:
                label, updated = self._extract_label_from_element(first)
                if label:
                    if updated is None:
                        cleaned = cleaned[1:]
                    else:
                        cleaned[0] = updated
                    return label, cleaned
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

    def _extract_label_from_element(
        self, node: RawElementNode
    ) -> tuple[Optional[str], Optional[RawElementNode]]:
        if not node.children:
            return None, node
        first = node.children[0]
        if not isinstance(first, RawTextNode):
            return None, node
        match = self.TEXT_LABEL_RE.match(first.value)
        if not match:
            return None, node
        label = self._normalize_label(match.group(1))
        remainder = first.value[match.end() :]
        new_children = list(node.children)
        if remainder.strip():
            new_children[0] = RawTextNode(value=remainder)
        else:
            new_children = new_children[1:]
        if not new_children:
            return label, None
        return label, RawElementNode(tag=node.tag, attrs=node.attrs, children=new_children)

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
        cleaned, _, label_found = self._extract_resources_nodes(
            nodes, resources, in_resources=False
        )
        if label_found:
            cleaned = self._trim_trailing_breaks(cleaned)
        return cleaned

    def _has_resource_label(self, nodes: List[RawNode]) -> bool:
        for node in nodes:
            if self._is_resource_label_node(node):
                return True
            if isinstance(node, RawElementNode) and self._has_resource_label(
                node.children
            ):
                return True
        return False

    def _extract_resources_nodes(
        self, nodes: List[RawNode], resources: List[Resource], in_resources: bool
    ) -> tuple[List[RawNode], bool, bool]:
        cleaned: List[RawNode] = []
        label_found = False
        for node in nodes:
            updated_node, in_resources, node_label_found = (
                self._extract_resources_from_node(node, resources, in_resources)
            )
            if node_label_found:
                label_found = True
            if updated_node is not None:
                cleaned.append(updated_node)
        return cleaned, in_resources, label_found

    def _extract_resources_from_node(
        self, node: RawNode, resources: List[Resource], in_resources: bool
    ) -> tuple[Optional[RawNode], bool, bool]:
        if isinstance(node, RawTextNode):
            if not in_resources and self.RESOURCE_LABEL_RE.match(node.value.strip()):
                return None, True, True
            if in_resources:
                return None, True, False
            return node, False, False

        if isinstance(node, RawElementNode):
            if not in_resources and self._is_resource_label_node(node):
                return None, True, True

            if node.tag == "a":
                if in_resources:
                    title = self._node_text(node).strip()
                    url = node.attrs.get("href", "")
                    if title and url:
                        resources.append(Resource(title=title, url=url))
                    return None, True, False
                return node, False, False

            if in_resources:
                _, _, label_found = self._extract_resources_nodes(
                    node.children, resources, in_resources=True
                )
                return None, True, label_found

            cleaned_children, child_in_resources, label_found = (
                self._extract_resources_nodes(
                    node.children, resources, in_resources=False
                )
            )
            if not cleaned_children:
                return None, child_in_resources, label_found
            return (
                RawElementNode(
                    tag=node.tag, attrs=node.attrs, children=cleaned_children
                ),
                child_in_resources,
                label_found,
            )

        return None, in_resources, False

    def _trim_trailing_breaks(self, nodes: List[RawNode]) -> List[RawNode]:
        while nodes and self._is_break(nodes[-1]):
            nodes.pop()
        return nodes

    def _is_resource_label_node(self, node: RawNode) -> bool:
        if isinstance(node, RawTextNode):
            return bool(self.RESOURCE_LABEL_RE.match(node.value.strip()))
        if isinstance(node, RawElementNode) and node.tag in self.RESOURCE_LABEL_TAGS:
            return bool(self.RESOURCE_LABEL_RE.match(self._node_text(node).strip()))
        return False

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
                if node.tag in {"b", "strong", "i", "em"}:
                    inline_children: List[RawNode] = []
                    for child in children:
                        if isinstance(child, RawElementNode) and child.tag == "br":
                            inline_children.append(RawTextNode(value=" "))
                        else:
                            inline_children.append(child)
                    children = inline_children
                attrs = {}
                if "href" in node.attrs:
                    attrs["href"] = node.attrs["href"]

                if node.tag not in {"b", "strong", "i", "em", "br", "a"}:
                    cleaned.extend(children)
                    continue

                if node.tag in {"b", "strong", "i", "em"}:
                    text = "".join(self._node_text(child) for child in children)
                    if not text.strip():
                        continue

                cleaned.append(
                    RawElementNode(tag=node.tag, attrs=attrs, children=children)
                )

        return self._merge_adjacent_text_nodes(cleaned)

    def _is_break(self, node: RawNode) -> bool:
        return isinstance(node, RawElementNode) and node.tag == "br"

    def _merge_adjacent_text_nodes(self, nodes: List[RawNode]) -> List[RawNode]:
        merged: List[RawNode] = []
        for node in nodes:
            if (
                isinstance(node, RawTextNode)
                and merged
                and isinstance(merged[-1], RawTextNode)
            ):
                prev_value = merged[-1].value
                next_value = node.value
                if prev_value and next_value:
                    if (
                        not prev_value.endswith((" ", "\n", "\t"))
                        and not next_value[0].isspace()
                        and next_value[0] not in ".,;:?!)]"
                    ):
                        prev_value += " "
                merged[-1] = RawTextNode(value=f"{prev_value}{next_value}")
            else:
                merged.append(node)
        return merged

    def _node_text(self, node: RawNode) -> str:
        if isinstance(node, RawTextNode):
            return node.value
        return "".join(self._node_text(child) for child in node.children)

    def _nodes_text(self, nodes: List[RawNode]) -> str:
        return "".join(self._node_text(node) for node in nodes)


class LabRequirementsExtractor:
    REQUIREMENT_START_RE = re.compile(r"^\s*(\d+)[.)]")
    LIST_STYLE_RE = re.compile(r"list-style-type\s*:\s*([^;]+)", re.IGNORECASE)
    SUPPORT_ITEMS_RE = re.compile(r"^\s*see support items\s*$", re.IGNORECASE)

    def __init__(
        self,
        extractor: Optional[HtmlExtractor] = None,
        processor: Optional[SemanticProcessor] = None,
    ) -> None:
        self._extractor = extractor or HtmlExtractor()
        self._processor = processor or SemanticProcessor()

    def extract_from_blocks(self, html_blocks: List[str]) -> List[SemanticRequirement]:
        raw_items: List[RawRequirementItem] = []
        for html in html_blocks:
            raw_items.extend(self._parse_html_block(html))
        return self._processor.process(raw_items)

    def _parse_html_block(self, html: str) -> List[RawRequirementItem]:
        soup = BeautifulSoup(html, "html.parser")
        container = soup.body if soup.body else soup
        if len(container.contents) == 1 and isinstance(container.contents[0], Tag):
            container = container.contents[0]

        requirements: List[RawRequirementItem] = []
        current_id: Optional[str] = None
        content_blocks: List[str] = []
        resource_blocks: List[Tag] = []
        sub_requirements: List[RawRequirementItem] = []
        sub_current_id: Optional[str] = None
        sub_content_blocks: List[str] = []
        sub_resource_blocks: List[Tag] = []
        sub_sub_requirements: List[RawRequirementItem] = []

        def finalize_sub() -> None:
            nonlocal sub_current_id, sub_content_blocks, sub_resource_blocks, sub_sub_requirements
            if sub_current_id is None:
                return
            sub_html = self._build_content_html(sub_content_blocks, sub_resource_blocks)
            sub_nodes = self._extractor.extract_nodes(sub_html)
            sub_requirements.append(
                RawRequirementItem(
                    id=sub_current_id or "",
                    content_nodes=sub_nodes,
                    sub_requirements=sub_sub_requirements,
                )
            )
            sub_current_id = None
            sub_content_blocks = []
            sub_resource_blocks = []
            sub_sub_requirements = []

        def finalize() -> None:
            nonlocal current_id, content_blocks, resource_blocks, sub_requirements
            if current_id is None:
                return
            finalize_sub()
            content_html = self._build_content_html(content_blocks, resource_blocks)
            content_nodes = self._extractor.extract_nodes(content_html)
            requirements.append(
                RawRequirementItem(
                    id=current_id,
                    content_nodes=content_nodes,
                    sub_requirements=sub_requirements,
                )
            )
            current_id = None
            content_blocks = []
            resource_blocks = []
            sub_requirements = []

        for child in container.contents:
            if isinstance(child, NavigableString):
                if not str(child).strip():
                    continue
                if current_id is not None:
                    content_blocks.append(str(child))
                continue
            if not isinstance(child, Tag):
                continue
            if self._is_empty_block(child):
                continue
            if self._is_requirement_start(child):
                finalize()
                current_id = self._extract_requirement_id(child)
                content_blocks = [child.decode_contents().strip()]
                continue

            if current_id is None:
                continue

            sub_label = self._extract_explicit_label(child.get_text(" ", strip=True))
            if sub_label and not self._is_requirement_start(child):
                finalize_sub()
                sub_current_id = sub_label
                sub_content_blocks = [child.decode_contents().strip()]
                continue

            if child.name in {"ul", "ol"}:
                if self._is_resource_list(child):
                    if sub_current_id is not None:
                        sub_resource_blocks.append(child)
                    else:
                        resource_blocks.append(child)
                else:
                    if sub_current_id is not None:
                        sub_sub_requirements.extend(self._parse_list(child))
                    else:
                        sub_requirements.extend(self._parse_list(child))
                continue

            if self._is_resource_block(child):
                if sub_current_id is not None:
                    sub_resource_blocks.append(child)
                else:
                    resource_blocks.append(child)
                continue

            if sub_current_id is not None:
                sub_content_blocks.append(child.decode_contents().strip())
            else:
                content_blocks.append(child.decode_contents().strip())

        finalize()
        return requirements

    def _parse_list(self, list_tag: Tag) -> List[RawRequirementItem]:
        items: List[RawRequirementItem] = []
        label_provider = self._label_provider(list_tag)
        for index, li in enumerate(list_tag.find_all("li", recursive=False)):
            if self._is_empty_block(li):
                continue
            content_parts: List[str] = []
            resource_blocks: List[Tag] = []
            sub_requirements: List[RawRequirementItem] = []

            for child in li.contents:
                if isinstance(child, Tag) and child.name in {"ul", "ol"}:
                    if self._is_resource_list(child):
                        resource_blocks.append(child)
                    else:
                        sub_requirements.extend(self._parse_list(child))
                else:
                    if isinstance(child, NavigableString) and not str(child).strip():
                        continue
                    content_parts.append(str(child))

            content_html = "".join(content_parts).strip()
            text = BeautifulSoup(content_html, "html.parser").get_text(" ", strip=True)
            label = self._extract_explicit_label(text)
            if label_provider and not label:
                label = label_provider(index)
                if label:
                    content_html = f"{label}. {content_html}".strip()
            if resource_blocks:
                content_html = self._append_resources(content_html, resource_blocks)
            content_nodes = self._extractor.extract_nodes(content_html)
            items.append(
                RawRequirementItem(
                    id=label or "",
                    content_nodes=content_nodes,
                    sub_requirements=sub_requirements,
                )
            )
        return items

    def _build_content_html(
        self, content_blocks: List[str], resource_blocks: List[Tag]
    ) -> str:
        parts: List[str] = []
        for block in content_blocks:
            inner = block.strip()
            if inner:
                parts.append(inner)
        content_html = "<br>".join(parts)
        if resource_blocks:
            content_html = self._append_resources(content_html, resource_blocks)
        return content_html

    def _append_resources(self, content_html: str, resource_blocks: List[Tag]) -> str:
        resources_html = "<em>Resources:</em>"
        for block in resource_blocks:
            resources_html += str(block)
        if content_html:
            return f"{content_html}<br>{resources_html}"
        return resources_html

    def _is_requirement_start(self, tag: Tag) -> bool:
        text = tag.get_text(" ", strip=True)
        return bool(self.REQUIREMENT_START_RE.match(text))

    def _extract_requirement_id(self, tag: Tag) -> str:
        text = tag.get_text(" ", strip=True)
        match = self.REQUIREMENT_START_RE.match(text)
        if not match:
            return ""
        return self._processor._normalize_label(match.group(0)) or ""

    def _extract_explicit_label(self, text: str) -> Optional[str]:
        match = self._processor.TEXT_LABEL_RE.match(text)
        if not match:
            return None
        return self._processor._normalize_label(match.group(1))

    def _is_resource_list(self, list_tag: Tag) -> bool:
        li_items = list_tag.find_all("li", recursive=False)
        if not li_items:
            return False
        for li in li_items:
            if li.find(["ul", "ol"], recursive=False):
                if self._li_is_resource_wrapper(li):
                    continue
                return False
            cloned = BeautifulSoup(str(li), "html.parser")
            for nested in cloned.find_all(["ul", "ol"]):
                nested.decompose()
            for anchor in cloned.find_all("a"):
                anchor.replace_with("")
            remaining = cloned.get_text(" ", strip=True)
            if remaining:
                return False
        return True

    def _is_resource_block(self, tag: Tag) -> bool:
        if tag.name not in {"p", "div"}:
            return False
        text = tag.get_text(" ", strip=True)
        if not text:
            return False
        if self.SUPPORT_ITEMS_RE.match(text):
            return True
        cloned = BeautifulSoup(str(tag), "html.parser")
        for anchor in cloned.find_all("a"):
            anchor.replace_with("")
        remaining = cloned.get_text(" ", strip=True)
        return remaining == ""

    def _li_is_resource_wrapper(self, li: Tag) -> bool:
        nested_lists = li.find_all(["ul", "ol"], recursive=False)
        if not nested_lists:
            return False
        cloned = BeautifulSoup(str(li), "html.parser")
        for nested in cloned.find_all(["ul", "ol"]):
            nested.decompose()
        for anchor in cloned.find_all("a"):
            anchor.replace_with("")
        remaining = cloned.get_text(" ", strip=True)
        if remaining:
            return False
        return all(self._is_resource_list(nested) for nested in nested_lists)

    def _label_provider(self, list_tag: Tag) -> Optional[Callable[[int], str]]:
        if list_tag.name != "ol":
            return None
        style = list_tag.get("style", "")
        match = self.LIST_STYLE_RE.search(style)
        list_type = match.group(1).strip().lower() if match else "decimal"
        if list_type == "none":
            return None

        def provider(index: int) -> str:
            if list_type in {"upper-alpha", "upper-latin"}:
                return chr(ord("A") + index)
            if list_type in {"lower-alpha", "lower-latin"}:
                return chr(ord("a") + index)
            if list_type == "upper-roman":
                return self._to_roman(index + 1).upper()
            if list_type == "lower-roman":
                return self._to_roman(index + 1).lower()
            return str(index + 1)

        return provider

    def _to_roman(self, number: int) -> str:
        if number <= 0:
            return ""
        numerals = [
            (1000, "M"),
            (900, "CM"),
            (500, "D"),
            (400, "CD"),
            (100, "C"),
            (90, "XC"),
            (50, "L"),
            (40, "XL"),
            (10, "X"),
            (9, "IX"),
            (5, "V"),
            (4, "IV"),
            (1, "I"),
        ]
        result = []
        remaining = number
        for value, numeral in numerals:
            while remaining >= value:
                result.append(numeral)
                remaining -= value
        return "".join(result)

    def _is_empty_block(self, tag: Tag) -> bool:
        text = tag.get_text(" ", strip=True)
        return not text or text == "\xa0"


class MarkdownGenerator:
    def generate(self, requirements: List[SemanticRequirement]) -> str:
        lines: List[str] = []
        for index, requirement in enumerate(requirements):
            if index > 0:
                lines.append("")
            lines.extend(self._render_requirement(requirement, level=0))
        return "\n".join(line.rstrip() for line in lines).rstrip()

    def render_content(self, nodes: List[RawNode]) -> str:
        content = self._render_nodes(nodes).strip()
        content = re.sub(r"\n[ \t]+", "\n", content)
        return content

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
                    inner = inner.strip()
                    parts.append(f"**{inner}**")
                elif node.tag in {"i", "em"}:
                    inner = inner.strip()
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
