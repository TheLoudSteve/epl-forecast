#!/usr/bin/env python3
"""
New Relic Alert Policy Setup Script for EPL Forecast Production
"""

import requests
import json
import os
from typing import Dict, List

class NewRelicAlertsManager:
    def __init__(self, api_key: str, account_id: str):
        self.api_key = api_key
        self.account_id = account_id
        self.base_url = "https://api.newrelic.com"
        self.headers = {
            "Api-Key": api_key,
            "Content-Type": "application/json"
        }
    
    def create_alert_policy(self, name: str, incident_preference: str = "PER_POLICY") -> Dict:
        """Create a new alert policy"""
        url = f"{self.base_url}/v2/alerts_policies.json"
        payload = {
            "policy": {
                "name": name,
                "incident_preference": incident_preference
            }
        }
        
        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()
        return response.json()["policy"]
    
    def create_nrql_condition(self, policy_id: int, condition_config: Dict) -> Dict:
        """Create NRQL alert condition"""
        url = f"{self.base_url}/v2/alerts_nrql_conditions/policies/{policy_id}.json"
        
        condition = {
            "nrql_condition": {
                "type": "static",
                "name": condition_config["name"],
                "enabled": True,
                "value_function": "single_value",
                "violation_time_limit_seconds": 2592000,
                "nrql": {
                    "query": condition_config["query"],
                    "since_value": "5"
                },
                "terms": []
            }
        }
        
        # Add critical threshold
        if "critical_threshold" in condition_config:
            critical = condition_config["critical_threshold"]
            condition["nrql_condition"]["terms"].append({
                "threshold": str(critical["value"]),
                "time_function": critical["time_function"],
                "duration": str(critical["duration_minutes"]),
                "operator": critical.get("operator", "above"),
                "priority": "critical"
            })
        
        # Add warning threshold
        if "warning_threshold" in condition_config:
            warning = condition_config["warning_threshold"]
            condition["nrql_condition"]["terms"].append({
                "threshold": str(warning["value"]),
                "time_function": warning["time_function"],
                "duration": str(warning["duration_minutes"]),
                "operator": warning.get("operator", "above"),
                "priority": "warning"
            })
        
        response = requests.post(url, headers=self.headers, json=condition)
        response.raise_for_status()
        return response.json()
    
    def create_notification_channel(self, name: str, email: str) -> Dict:
        """Create email notification channel"""
        url = f"{self.base_url}/v2/alerts_channels.json"
        payload = {
            "channel": {
                "name": name,
                "type": "email",
                "configuration": {
                    "recipients": email,
                    "include_json_attachment": "1"
                }
            }
        }
        
        response = requests.post(url, headers=self.headers, json=payload)
        if response.status_code != 201:
            print(f"Error creating notification channel: {response.status_code}")
            print(f"Response: {response.text}")
            response.raise_for_status()
        
        result = response.json()
        print(f"API Response: {result}")
        
        # Handle different response formats
        if "channel" in result:
            return result["channel"]
        elif "channels" in result:
            return result["channels"][0]
        else:
            return result
    
    def update_policy_channels(self, policy_id: int, channel_ids: List[int]):
        """Associate notification channels with alert policy"""
        # Try the newer format first
        url = f"{self.base_url}/v2/alerts_policy_channels.json?policy_id={policy_id}&channel_ids={','.join(map(str, channel_ids))}"
        
        print(f"Associating channels {channel_ids} with policy {policy_id}")
        
        response = requests.put(url, headers=self.headers)
        
        if response.status_code not in [200, 201]:
            print(f"Error associating channels: {response.status_code}")
            print(f"Response: {response.text}")
            print(f"Manual setup required: Go to New Relic UI to associate notification channels")
            return None
        
        return response.json()

def setup_epl_forecast_alerts():
    """Set up all EPL Forecast alert policies and conditions"""
    
    # Get credentials from environment
    api_key = os.getenv("NEW_RELIC_USER_API_KEY")
    account_id = os.getenv("NEW_RELIC_ACCOUNT_ID", "7052187")
    notification_email = os.getenv("NOTIFICATION_EMAIL", "your-email@domain.com")
    
    if not api_key:
        print("Error: NEW_RELIC_USER_API_KEY environment variable required")
        return
    
    # Initialize manager
    manager = NewRelicAlertsManager(api_key, account_id)
    
    # Load alert configuration
    with open("newrelic-alerts.json", "r") as f:
        config = json.load(f)
    
    # Create notification channel
    print(f"Creating notification channel for {notification_email}...")
    channel = manager.create_notification_channel("EPL Forecast Email Alerts", notification_email)
    channel_id = channel["id"]
    print(f"Created channel ID: {channel_id}")
    
    # Create alert policies and conditions
    for policy_config in config["alert_policies"]:
        print(f"Creating alert policy: {policy_config['name']}")
        
        # Create policy
        policy = manager.create_alert_policy(
            policy_config["name"],
            policy_config["incident_preference"]
        )
        policy_id = policy["id"]
        print(f"Created policy ID: {policy_id}")
        
        # Create conditions
        for condition_config in policy_config["conditions"]:
            if condition_config["type"] == "NRQL":
                print(f"  Creating NRQL condition: {condition_config['name']}")
                manager.create_nrql_condition(policy_id, condition_config)
            else:
                print(f"  Skipping {condition_config['type']} condition (manual setup required)")
        
        # Associate notification channel
        print(f"  Associating notification channel...")
        result = manager.update_policy_channels(policy_id, [channel_id])
        if result is None:
            print(f"  Warning: Could not associate notification channel with policy {policy_id}")
        
        print(f"Completed setup for policy: {policy_config['name']}\n")
    
    print("Alert setup completed successfully!")
    print("\nManual setup required for:")
    print("- Mobile app crash rate conditions")
    print("- Mobile app load time conditions")
    print("- Update notification email in the script or environment variable")

if __name__ == "__main__":
    setup_epl_forecast_alerts()