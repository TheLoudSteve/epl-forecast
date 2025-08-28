#!/usr/bin/env python3
"""
New Relic Dashboard Creation Script for EPL Forecast Production
"""

import requests
import json
import os
from typing import Dict

class NewRelicDashboardManager:
    def __init__(self, api_key: str, account_id: str):
        self.api_key = api_key
        self.account_id = account_id
        self.base_url = "https://api.newrelic.com/graphql"
        self.headers = {
            "Api-Key": api_key,
            "Content-Type": "application/json"
        }
    
    def create_dashboard(self, dashboard_config: Dict) -> Dict:
        """Create dashboard using NerdGraph GraphQL API"""
        
        # Convert JSON config to GraphQL mutation format
        dashboard_input = self._convert_to_graphql_input(dashboard_config)
        
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
        
        variables = {
            "accountId": int(self.account_id),
            "dashboard": dashboard_input
        }
        
        payload = {
            "query": mutation,
            "variables": variables
        }
        
        print("Creating EPL Forecast dashboard...")
        print(f"Dashboard name: {dashboard_config['dashboard']['name']}")
        
        response = requests.post(self.base_url, headers=self.headers, json=payload)
        
        if response.status_code != 200:
            print(f"HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
            response.raise_for_status()
        
        result = response.json()
        
        if "errors" in result:
            print(f"GraphQL Errors: {result['errors']}")
            return None
        
        if not result.get("data"):
            print(f"No data in response: {result}")
            return None
        
        dashboard_create = result["data"].get("dashboardCreate")
        if not dashboard_create:
            print(f"No dashboardCreate in response: {result}")
            return None
        
        if dashboard_create.get("errors"):
            errors = dashboard_create["errors"]
            print(f"Dashboard Creation Errors: {errors}")
            return None
        
        entity_result = dashboard_create.get("entityResult")
        if not entity_result:
            print(f"No entityResult in response: {result}")
            return None
        
        print(f"Dashboard created successfully!")
        print(f"GUID: {entity_result['guid']}")
        print(f"Name: {entity_result['name']}")
        
        # Construct dashboard URL manually
        dashboard_url = f"https://one.newrelic.com/dashboards/detail/{entity_result['guid']}"
        print(f"URL: {dashboard_url}")
        
        return {
            "guid": entity_result["guid"],
            "name": entity_result["name"],
            "url": dashboard_url
        }
    
    def _convert_to_graphql_input(self, config: Dict) -> Dict:
        """Convert JSON config to GraphQL DashboardInput format"""
        dashboard = config["dashboard"]
        
        return {
            "name": dashboard["name"],
            "description": dashboard["description"],
            "permissions": dashboard["permissions"],
            "pages": [
                {
                    "name": page["name"],
                    "description": page["description"],
                    "widgets": [
                        {
                            "title": widget["title"],
                            "layout": {
                                "column": widget["layout"]["column"],
                                "row": widget["layout"]["row"],
                                "width": widget["layout"]["width"],
                                "height": widget["layout"]["height"]
                            },
                            "visualization": {
                                "id": widget["visualization"]["id"]
                            },
                            "rawConfiguration": widget["rawConfiguration"]
                        }
                        for widget in page["widgets"]
                    ]
                }
                for page in dashboard["pages"]
            ]
        }

def setup_epl_forecast_dashboard():
    """Set up EPL Forecast monitoring dashboard"""
    
    # Get credentials from environment
    api_key = os.getenv("NEW_RELIC_USER_API_KEY")
    account_id = os.getenv("NEW_RELIC_ACCOUNT_ID", "7052187")
    
    if not api_key:
        print("Error: NEW_RELIC_USER_API_KEY environment variable required")
        print("Get your User API Key from: https://one.newrelic.com/api-keys")
        return
    
    # Initialize manager
    manager = NewRelicDashboardManager(api_key, account_id)
    
    # Load dashboard configuration
    try:
        with open("dashboard-config.json", "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("Error: dashboard-config.json file not found")
        return
    except json.JSONDecodeError as e:
        print(f"Error parsing dashboard-config.json: {e}")
        return
    
    # Create dashboard
    result = manager.create_dashboard(config)
    
    if result:
        print("\n" + "="*60)
        print("DASHBOARD SETUP COMPLETED SUCCESSFULLY!")
        print("="*60)
        print(f"Dashboard Name: {result['name']}")
        print(f"Dashboard URL: {result['url']}")
        print(f"Dashboard GUID: {result['guid']}")
        print("\nYour EPL Forecast monitoring dashboard is now live!")
        print("Bookmark the URL above for easy access.")
    else:
        print("Dashboard creation failed. Check the error messages above.")

if __name__ == "__main__":
    setup_epl_forecast_dashboard()