{% macro escape_starting_asterisk(text) %}
{%- if text.startswith('*') %}
\{{ text }}
{%- else %}
{{ text }}
{%- endif %}
{%- endmacro %}

{% macro render_requirements(requirements, level=0) %}
{% set indent = ' ' * (level * 4) %}
{% for requirement in requirements %}
{{ indent }}* {% if requirement.id %}({{ requirement.id }}) {% endif %}{{ escape_starting_asterisk(requirement.text) }}
{% if requirement.requirements %}{{ render_requirements(requirement.requirements, level + 1) }}

{% endif %}
{% endfor %}
{% endmacro %}

# {{ badge_name }} Merit Badge

{% if badge_image_filename %}
![{{ badge_name }} Merit Badge](images/{{ badge_image_filename }})
{% endif %}

## Overview

{% if is_eagle_required %}**Eagle required**{% endif %}


{{ badge_overview }}

## Requirements

{{ render_requirements(requirements_data) }}

## Resources

- [{{ badge_name }} merit badge page]({{ badge_url }})
{% if badge_pdf_url and files and files|length > 0 %}
- [{{ badge_name }} merit badge PDF]({{ badge_pdf_url }}) ([local copy](files/{{ files[0].path }}))
{% elif badge_pdf_url %}
- [{{ badge_name }} merit badge PDF]({{ badge_pdf_url }})
{% endif %}
- [{{ badge_name }} merit badge pamphlet]({{ badge_shop_url }})
{% if workbook_pdf_url %}
- [{{ badge_name }} merit badge workbook PDF]({{ workbook_pdf_url }})
{% endif %}
{% if workbook_docx_url %}
- [{{ badge_name }} merit badge workbook DOCX]({{ workbook_docx_url }})
{% endif %}

Note: This is an unofficial archive of Scouts BSA Merit Badges that was automatically extracted from the Scouting America website and may contain errors.
