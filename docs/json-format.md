# JSON Format

This repository writes structured JSON for two archive types:

- Merit badges: `build/merit-badges/*.json`
- Cub Scout adventures: `build/cub-scout-adventures/{rank}/*.json`

The JSON is emitted by `src/scout_archive/pipelines.py`. Fields can be empty
strings or `null` when the source page omits data.

## Merit Badge JSON

Top-level object:

- `name` (string): Badge name with "Merit Badge" removed.
- `overview` (string): Overview paragraph(s). May be empty.
- `is_eagle_required` (boolean): True when the page marks the badge as Eagle required.
- `is_lab` (boolean): True for Merit Badge Test Lab badges.
- `url` (string): Badge page URL.
- `pdf_url` (string): Link to the badge pamphlet PDF (empty string if missing).
- `workbook_pdf_url` (string | null): Worksheet PDF from usscouts.org (null if missing).
- `workbook_docx_url` (string | null): Worksheet DOCX from usscouts.org (null if missing).
- `shop_url` (string | null): Scout Shop link (null/empty if missing).
- `image_url` (string): Badge image URL (empty string if missing).
- `image_filename` (string): Local image filename in `build/merit-badges/images/`.
- `requirements` (array): Requirement tree (see below).

Requirement object (semantic tree):

- `id` (string): Internal DOM id for standard merit badges. For Test Lab badges
  this may match the displayed requirement number. Do **not** treat this as a
  stable identifier.
- `label` (string | null): Normalized display label (e.g., `"1"`, `"a"`).
- `text` (string): Flattened plain-text content for display, search, and
  downstream renderers. This excludes child requirement text and resource links.
- `requirement_path` (string): Stable best-effort semantic path derived from
  the visible hierarchy (e.g., `"1"`, `"1.a"`, `"2.option-a.3.b"`).
- `node_kind` (string): One of `"action_requirement"`,
  `"instruction_container"`, or `"option_container"`.
- `is_container` (boolean): True when the node owns child requirements.
- `requires_response` (boolean): True when the node is an answerable/action
  requirement; false for pure instruction and option containers.
- `scoped_clauses` (array): Exact substrings of `text` whose action scope can
  be inferred from the semantic tree (see below). This list is not intended to
  be an exhaustive grammatical decomposition.
- `content` (array): Requirement content as a semantic HTML node list.
- `resources` (array): Resource links (see below).
- `sub_requirements` (array): Child requirements.

Raw node object (`content` tree):

- Text node: `{ "type": "text", "value": "..." }`
- Element node: `{ "type": "element", "tag": "b" | "i" | "em" | "strong" | "a" | "br", "attrs": { "href": "..." }, "children": [...] }`

Resource object:

- `title` (string)
- `url` (string)

Scoped clause object:

- `text` (string): An exact substring of the owning requirement's normalized
  `text`.
- `scope` (string): One of `"requirement"`, `"children"`, or `"ambiguous"`.
  A requirement-scoped clause is performed once at the owning node and must
  not be inherited by its children. A children-scoped clause governs each
  direct child and is the parent context downstream consumers should inherit.
  An ambiguous clause combines or follows actions whose ownership cannot be
  separated conservatively; consumers must not assume that it applies to every
  child.

Notes:

- Use `label` for numbering in UIs; `id` is internal/unstable.
- The `requirements` array is hierarchical; each node owns its children.
- `requires_response` remains a coarse, node-level compatibility signal, while
  `scoped_clauses` is authoritative when deciding which portions of a
  container's text to inherit. On a mixed container, a `requirement` clause
  keeps `requires_response` true even when another clause only introduces
  children.
  An empty `scoped_clauses` list means no clause scope was inferred or the node
  has no children; consumers of older archives should fall back to their
  existing node-level behavior.
- When an alphabetic action requirement or named option clearly introduces a
  contiguous numbered list, those numbered entries are children of that action.
  Their `requirement_path` values include the governing action path (for example,
  `"1.b.1"` rather than `"1.1"`). Source content, resources, and `id` values are
  unchanged by this semantic hierarchy repair.

Example (truncated):

```json
{
  "name": "Camping",
  "overview": "The Camping merit badge...",
  "is_eagle_required": true,
  "is_lab": false,
  "url": "https://www.scouting.org/merit-badges/camping/",
  "pdf_url": "https://...",
  "workbook_pdf_url": "https://...",
  "workbook_docx_url": "https://...",
  "shop_url": "https://...",
  "image_url": "https://...",
  "image_filename": "camping-merit-badge.jpg",
  "requirements": [
    {
      "id": "123",
      "label": "1",
      "text": "Discuss the following:",
      "requirement_path": "1",
      "node_kind": "instruction_container",
      "is_container": true,
      "requires_response": false,
      "scoped_clauses": [
        { "text": "Discuss the following:", "scope": "children" }
      ],
      "content": [
        { "type": "text", "value": "Discuss the following:" }
      ],
      "resources": [],
      "sub_requirements": [
        {
          "id": "124",
          "label": "a",
          "text": "Explain...",
          "requirement_path": "1.a",
          "node_kind": "action_requirement",
          "is_container": false,
          "requires_response": true,
          "scoped_clauses": [],
          "content": [
            { "type": "text", "value": "Explain..." }
          ],
          "resources": [],
          "sub_requirements": []
        }
      ]
    }
  ]
}
```

## Cub Scout Adventure JSON

Top-level object:

- `rank_name` (string): Rank name (e.g., `"Wolf"`). Falls back to `"Unknown"`.
- `adventure_name` (string): Adventure title.
- `adventure_type` (string): `"Required"`, `"Elective"`, or `"Special"` (may be empty).
- `adventure_category` (string): Category label (may be empty).
- `adventure_overview` (string): Overview paragraph(s) (may be empty).
- `url` (string): Adventure page URL.
- `image_url` (string): Adventure image URL (may be empty).
- `image_filename` (string): Local image filename in `build/cub-scout-adventures/{rank}/images/`.
- `requirements` (array): Requirement list (see below).

Requirement object:

- `id` (string): Requirement number from the page (e.g., `"1"`).
- `label` (string | null): Display label (typically the same as `id`).
- `text` (string): Flattened text version for quick display/search.
- `requirement_path` (string): Stable best-effort semantic path derived from
  the visible hierarchy.
- `node_kind` (string): One of `"action_requirement"`,
  `"instruction_container"`, or `"option_container"`.
- `is_container` (boolean): True when the node owns child requirements.
- `requires_response` (boolean): True when the node is an answerable/action
  requirement; false for pure instruction and option containers.
- `scoped_clauses` (array): Exact text clauses with the same scope contract as
  merit badge requirements above.
- `content` (array): Requirement content as a semantic HTML node list.
- `resources` (array): Resource links.
- `sub_requirements` (array): Child requirements.
- `activities` (array): Activity list (see below). May be empty.

Activity object:

- `name` (string): Activity title.
- `url` (string): Activity URL.
- `description` (string): Activity description.
- `location` (string): `"Indoor"`, `"Outdoor"`, `"Travel"`, or empty.
- `energy_level` (string): `"1"`-`"5"` rating or empty.
- `supply_list` (string): `"1"`-`"5"` rating or empty.
- `prep_time` (string): `"1"`-`"5"` rating or empty.

Example (truncated):

```json
{
  "rank_name": "Wolf",
  "adventure_name": "Paws on the Path",
  "adventure_type": "Required",
  "adventure_category": "Outdoor",
  "adventure_overview": "In this adventure...",
  "url": "https://www.scouting.org/cub-scout-adventures/paws-on-the-path/",
  "image_url": "https://...",
  "image_filename": "paws-on-the-path.jpg",
  "requirements": [
    {
      "id": "1",
      "label": "1",
      "text": "Show you are prepared...",
      "requirement_path": "1",
      "node_kind": "action_requirement",
      "is_container": false,
      "requires_response": true,
      "scoped_clauses": [],
      "content": [
        { "type": "text", "value": "Show you are prepared..." }
      ],
      "resources": [],
      "sub_requirements": [],
      "activities": [
        {
          "name": "Trail Safety Check",
          "url": "https://...",
          "description": "Discuss safety...",
          "location": "Outdoor",
          "energy_level": "2",
          "supply_list": "2",
          "prep_time": "1"
        }
      ]
    }
  ]
}
```
