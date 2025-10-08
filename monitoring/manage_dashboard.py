#!/usr/bin/env python3
"""
Manage New Relic dashboards using NerdGraph API

Usage:
    export NEW_RELIC_API_KEY=your_user_key_here

    # Smart sync - find dashboard by name and update, or create if doesn't exist
    python3 manage_dashboard.py sync new-relic-dashboard.json

    # Export existing dashboard
    python3 manage_dashboard.py export <dashboard-guid>

    # Update specific dashboard
    python3 manage_dashboard.py update <dashboard-guid> new-relic-dashboard.json

    # Create new dashboard
    python3 manage_dashboard.py create new-relic-dashboard.json

Get your User API key from: https://one.newrelic.com/admin-portal/api-keys/home
"""

import json
import os
import sys
import requests


def get_api_key():
    """Get API key from environment"""
    api_key = os.environ.get('NEW_RELIC_API_KEY')
    if not api_key:
        print("ERROR: NEW_RELIC_API_KEY environment variable not set")
        print("Get your User API key from: https://one.newrelic.com/admin-portal/api-keys/home")
        sys.exit(1)
    return api_key


def nerdgraph_query(api_key, query, variables=None):
    """Execute NerdGraph query"""
    response = requests.post(
        'https://api.newrelic.com/graphql',
        headers={
            'Content-Type': 'application/json',
            'API-Key': api_key
        },
        json={
            'query': query,
            'variables': variables or {}
        }
    )

    result = response.json()

    if 'errors' in result:
        print("GraphQL Errors:")
        print(json.dumps(result['errors'], indent=2))
        sys.exit(1)

    return result


def export_dashboard(api_key, guid):
    """Export existing dashboard to see correct format"""
    query = """
    query($guid: EntityGuid!) {
      actor {
        entity(guid: $guid) {
          ... on DashboardEntity {
            name
            description
            permissions
            pages {
              name
              description
              widgets {
                title
                layout {
                  column
                  row
                  width
                  height
                }
                visualization {
                  id
                }
                rawConfiguration
              }
            }
            variables {
              name
              title
              type
              defaultValues {
                value {
                  string
                }
              }
              items {
                title
                value
              }
              isMultiSelection
              nrqlQuery {
                accountIds
                query
              }
              replacementStrategy
            }
          }
        }
      }
    }
    """

    result = nerdgraph_query(api_key, query, {'guid': guid})
    dashboard = result['data']['actor']['entity']

    # Save to file
    output_file = 'exported-dashboard.json'
    with open(output_file, 'w') as f:
        json.dump(dashboard, f, indent=2)

    print(f"✅ Dashboard exported to {output_file}")
    print(f"   Name: {dashboard['name']}")
    print(f"   Pages: {len(dashboard['pages'])}")

    return dashboard


def update_dashboard(api_key, guid, dashboard_file):
    """Update existing dashboard"""
    with open(dashboard_file, 'r') as f:
        dashboard_data = json.load(f)

    # Build dashboard input from file
    dashboard_input = {
        'name': dashboard_data['name'],
        'description': dashboard_data.get('description', ''),
        'permissions': dashboard_data.get('permissions', 'PUBLIC_READ_WRITE'),
        'pages': dashboard_data['pages']
    }

    if 'variables' in dashboard_data:
        dashboard_input['variables'] = dashboard_data['variables']

    mutation = """
    mutation($guid: EntityGuid!, $dashboard: DashboardInput!) {
      dashboardUpdate(guid: $guid, dashboard: $dashboard) {
        entityResult {
          guid
          name
        }
        errors {
          description
          type
        }
      }
    }
    """

    result = nerdgraph_query(api_key, mutation, {
        'guid': guid,
        'dashboard': dashboard_input
    })

    data = result['data']['dashboardUpdate']
    errors = data.get('errors', [])

    if errors:
        print("Dashboard Update Errors:")
        for error in errors:
            print(f"  - {error['type']}: {error['description']}")
        sys.exit(1)

    entity = data['entityResult']
    print(f"✅ Dashboard updated successfully!")
    print(f"   GUID: {entity['guid']}")
    print(f"   Name: {entity['name']}")
    print(f"   URL: https://one.newrelic.com/dashboards/{entity['guid']}")


def create_dashboard(api_key, dashboard_file):
    """Create new dashboard"""
    with open(dashboard_file, 'r') as f:
        dashboard_data = json.load(f)

    mutation = """
    mutation($accountId: Int!, $dashboard: DashboardInput!) {
      dashboardCreate(accountId: $accountId, dashboard: $dashboard) {
        entityResult {
          guid
          name
        }
        errors {
          description
          type
        }
      }
    }
    """

    result = nerdgraph_query(api_key, mutation, {
        'accountId': 7052187,
        'dashboard': dashboard_data
    })

    data = result['data']['dashboardCreate']
    errors = data.get('errors', [])

    if errors:
        print("Dashboard Creation Errors:")
        for error in errors:
            print(f"  - {error['type']}: {error['description']}")
        sys.exit(1)

    entity = data['entityResult']
    print(f"✅ Dashboard created successfully!")
    print(f"   GUID: {entity['guid']}")
    print(f"   Name: {entity['name']}")
    print(f"   URL: https://one.newrelic.com/dashboards/{entity['guid']}")


def find_dashboard_by_name(api_key, name, account_id=7052187):
    """Find dashboard by name"""
    query = """
    query($searchQuery: String!) {
      actor {
        entitySearch(query: $searchQuery) {
          results {
            entities {
              guid
              name
              accountId
              ... on DashboardEntityOutline {
                guid
                name
              }
            }
          }
        }
      }
    }
    """

    # Search for dashboards with the name
    search_query = f"type = 'DASHBOARD' AND name = '{name}' AND accountId = {account_id}"

    result = nerdgraph_query(api_key, query, {
        'searchQuery': search_query
    })

    entities = result.get('data', {}).get('actor', {}).get('entitySearch', {}).get('results', {}).get('entities', [])

    # Filter to exact name match
    for entity in entities:
        if entity.get('name') == name and entity.get('accountId') == account_id:
            return entity.get('guid')

    return None


def sync_dashboard(api_key, dashboard_file, account_id=7052187):
    """Find dashboard by name and update it, or create if it doesn't exist"""
    with open(dashboard_file, 'r') as f:
        dashboard_data = json.load(f)

    dashboard_name = dashboard_data.get('name', 'EPLF')

    print(f"Looking for dashboard named '{dashboard_name}'...")
    guid = find_dashboard_by_name(api_key, dashboard_name, account_id)

    if guid:
        print(f"✅ Found existing dashboard: {guid}")
        print(f"   Updating dashboard...")
        update_dashboard(api_key, guid, dashboard_file)
    else:
        print(f"⚠️  Dashboard '{dashboard_name}' not found")
        print(f"   Creating new dashboard...")
        create_dashboard(api_key, dashboard_file)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    api_key = get_api_key()

    if command == 'sync':
        # Smart sync - find by name and update, or create if not exists
        if len(sys.argv) < 3:
            print("Usage: manage_dashboard.py sync <json-file>")
            sys.exit(1)
        json_file = sys.argv[2]
        sync_dashboard(api_key, json_file)

    elif command == 'export':
        if len(sys.argv) < 3:
            print("Usage: manage_dashboard.py export <dashboard-guid>")
            sys.exit(1)
        guid = sys.argv[2]
        export_dashboard(api_key, guid)

    elif command == 'update':
        if len(sys.argv) < 4:
            print("Usage: manage_dashboard.py update <dashboard-guid> <json-file>")
            sys.exit(1)
        guid = sys.argv[2]
        json_file = sys.argv[3]
        update_dashboard(api_key, guid, json_file)

    elif command == 'create':
        if len(sys.argv) < 3:
            print("Usage: manage_dashboard.py create <json-file>")
            sys.exit(1)
        json_file = sys.argv[2]
        create_dashboard(api_key, json_file)

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == '__main__':
    main()
