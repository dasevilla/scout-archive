# {{ adventure_name }} {{ rank_name }} Adventure

{% if adventure_image_filename %}![{{ adventure_name }} {{ rank_name }} adventure belt loop](images/{{ adventure_image_filename }})
{% endif %}

- **Adventure name:** {{ adventure_name }}
- **Rank:** {{ rank_name }}
- **Type:** {{ adventure_type }}
- **Category:** {{ adventure_category }}

## Overview

{{ adventure_overview }}

## Requirements

{% for requirement in requirements_data %}
### Requirement {{ requirement.id }}

{{ requirement.text }}

{% if requirement.activities %}
**Activities:**

{% for activity in requirement.activities %}
- **[{{ activity.name }}]({{ activity.url }})** ({{ activity.location }}{% if activity.energy_level %}, energy {{ activity.energy_level }}{% endif %}{% if activity.supply_list %}, supplies {{ activity.supply_list }}{% endif %}{% if activity.prep_time %}, prep {{ activity.prep_time }}{% endif %})
  {{ activity.description }}
{% endfor %}
{% endif %}

{% endfor %}

## Resources

- [{{ adventure_name }} {{ rank_name }} adventure page]({{ adventure_url }})

Note: This is an unofficial archive of Cub Scout Adventures that was automatically extracted from the Scouting America website and may contain errors.
