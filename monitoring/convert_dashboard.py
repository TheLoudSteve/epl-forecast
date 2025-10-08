#!/usr/bin/env python3
"""
Convert dashboard JSON to New Relic-compatible format
"""

import json
import sys


def clean_widget(widget):
    """Clean widget configuration"""
    cleaned = {
        'title': widget.get('title'),
        'layout': widget.get('layout'),
        'visualization': widget.get('visualization'),
    }

    # Handle rawConfiguration - remove unsupported fields
    if 'rawConfiguration' in widget:
        raw_config = widget['rawConfiguration']
        cleaned_config = {}

        # Keep only nrqlQueries
        if 'nrqlQueries' in raw_config:
            cleaned_config['nrqlQueries'] = raw_config['nrqlQueries']

        # Note: thresholds are not supported in rawConfiguration via API
        # They need to be set via UI after dashboard creation

        cleaned['rawConfiguration'] = cleaned_config

    return cleaned


def clean_variables(variables):
    """Clean variables to supported format"""
    if not variables:
        return []

    cleaned_vars = []
    for var in variables:
        # Variables need simpler format
        cleaned_var = {
            'name': var.get('name'),
            'type': var.get('type', 'NRQL').upper(),  # ENUM or NRQL
        }

        # Add optional fields if present
        if 'title' in var:
            cleaned_var['title'] = var['title']

        if 'defaultValues' in var and var['defaultValues']:
            # Simplify default values
            default = var['defaultValues'][0]
            if 'value' in default and 'string' in default['value']:
                cleaned_var['defaultValues'] = [{
                    'value': {
                        'string': default['value']['string']
                    }
                }]

        if 'isMultiSelection' in var:
            cleaned_var['isMultiSelection'] = var['isMultiSelection']

        # For ENUM type, we need items
        if var.get('type') == 'enum' and 'items' in var:
            cleaned_var['items'] = var['items']

        # For NRQL type, we need nrqlQuery
        if var.get('type') == 'NRQL' and 'nrqlQuery' in var:
            cleaned_var['nrqlQuery'] = var['nrqlQuery']

        cleaned_vars.append(cleaned_var)

    return cleaned_vars


def convert_dashboard(input_file, output_file):
    """Convert dashboard to New Relic-compatible format"""
    with open(input_file, 'r') as f:
        dashboard = json.load(f)

    cleaned = {
        'name': dashboard.get('name'),
        'description': dashboard.get('description', ''),
        'permissions': dashboard.get('permissions', 'PUBLIC_READ_WRITE'),
        'pages': []
    }

    # Clean pages and widgets
    for page in dashboard.get('pages', []):
        cleaned_page = {
            'name': page.get('name'),
            'description': page.get('description'),
            'widgets': []
        }

        for widget in page.get('widgets', []):
            cleaned_page['widgets'].append(clean_widget(widget))

        cleaned['pages'].append(cleaned_page)

    # Clean variables
    if 'variables' in dashboard:
        cleaned_vars = clean_variables(dashboard['variables'])
        if cleaned_vars:
            cleaned['variables'] = cleaned_vars

    # Save cleaned version
    with open(output_file, 'w') as f:
        json.dump(cleaned, f, indent=2)

    print(f"✅ Converted dashboard saved to {output_file}")
    print(f"   Note: Thresholds removed (not supported via API)")
    print(f"   You can add thresholds manually in the UI after creation")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: convert_dashboard.py <input-file> [output-file]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'dashboard-converted.json'

    convert_dashboard(input_file, output_file)
