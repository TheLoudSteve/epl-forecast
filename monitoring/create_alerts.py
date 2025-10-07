"""
Create New Relic Alert Policy and Conditions for EPL Forecast Production

EPLF-53: Add New Relic Alert Policy for Production Monitoring
"""

import os
import requests
import json

# New Relic configuration
NR_ACCOUNT_ID = "7052187"
NR_API_KEY = os.environ.get('NEW_RELIC_USER_API_KEY')  # User API key required
NR_GRAPHQL_URL = "https://api.newrelic.com/graphql"

if not NR_API_KEY:
    print("ERROR: NEW_RELIC_USER_API_KEY environment variable not set")
    print("Get your User API key from: https://one.newrelic.com/api-keys")
    exit(1)

def run_graphql(query, variables=None):
    """Execute a NerdGraph GraphQL query"""
    headers = {
        "Content-Type": "application/json",
        "API-Key": NR_API_KEY
    }

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    response = requests.post(NR_GRAPHQL_URL, headers=headers, json=payload)
    response.raise_for_status()

    result = response.json()
    if "errors" in result:
        print(f"GraphQL Errors: {json.dumps(result['errors'], indent=2)}")
        raise Exception(f"GraphQL query failed: {result['errors']}")

    return result["data"]


def get_or_create_alert_policy():
    """Get existing policy or create new one: EPL Forecast Production"""
    print("📋 Checking for existing alert policy...")

    # First, try to find existing policy by listing all and filtering
    search_query = """
    query($accountId: Int!) {
      actor {
        account(id: $accountId) {
          alerts {
            policiesSearch {
              policies {
                id
                name
              }
            }
          }
        }
      }
    }
    """

    search_variables = {
        "accountId": int(NR_ACCOUNT_ID)
    }

    result = run_graphql(search_query, search_variables)
    all_policies = result["actor"]["account"]["alerts"]["policiesSearch"]["policies"]

    # Find our specific policy
    for policy in all_policies:
        if policy["name"] == "EPL Forecast Production":
            policy_id = policy["id"]
            print(f"✅ Found existing policy: {policy_id}")
            return policy_id

    # Policy doesn't exist, create it
    print("📋 Creating new alert policy...")

    create_query = """
    mutation($accountId: Int!, $policy: AlertsPolicyInput!) {
      alertsPolicyCreate(accountId: $accountId, policy: $policy) {
        id
        name
        incidentPreference
      }
    }
    """

    create_variables = {
        "accountId": int(NR_ACCOUNT_ID),
        "policy": {
            "name": "EPL Forecast Production",
            "incidentPreference": "PER_CONDITION"
        }
    }

    result = run_graphql(create_query, create_variables)
    policy_id = result["alertsPolicyCreate"]["id"]
    print(f"✅ Created policy: {policy_id}")
    return policy_id


def find_workflow_for_slack():
    """Find existing workflow that uses loudsteve Slack destination"""
    print("🔍 Finding workflow with 'loudsteve' Slack destination...")

    query = """
    query($accountId: Int!) {
      actor {
        account(id: $accountId) {
          aiWorkflows {
            workflows {
              entities {
                id
                name
                destinationConfigurations {
                  name
                }
              }
            }
          }
        }
      }
    }
    """

    variables = {"accountId": int(NR_ACCOUNT_ID)}
    result = run_graphql(query, variables)

    workflows = result["actor"]["account"]["aiWorkflows"]["workflows"]["entities"]
    for workflow in workflows:
        for dest_config in workflow["destinationConfigurations"]:
            if "loudsteve" in dest_config["name"].lower():
                print(f"✅ Found existing workflow: {workflow['id']} - {workflow['name']}")
                return workflow["id"]

    print("⚠️  No existing workflow found with 'loudsteve' destination")
    print("   Alert policy will be created but notifications need manual setup")
    print("   Link the policy to your Slack destination in the New Relic UI")
    return None


def get_existing_conditions(policy_id):
    """Get list of existing conditions for a policy"""
    query = """
    query($accountId: Int!, $policyId: ID!) {
      actor {
        account(id: $accountId) {
          alerts {
            nrqlConditionsSearch(searchCriteria: {policyId: $policyId}) {
              nrqlConditions {
                id
                name
              }
            }
          }
        }
      }
    }
    """

    variables = {
        "accountId": int(NR_ACCOUNT_ID),
        "policyId": policy_id
    }

    result = run_graphql(query, variables)
    conditions = result["actor"]["account"]["alerts"]["nrqlConditionsSearch"]["nrqlConditions"]
    return {cond["name"]: cond["id"] for cond in conditions}


def create_or_skip_condition(policy_id, condition_config, existing_conditions):
    """Create a NRQL static alert condition if it doesn't exist"""
    condition_name = condition_config["name"]

    # Check if condition already exists
    if condition_name in existing_conditions:
        condition_id = existing_conditions[condition_name]
        print(f"⏭️  Condition already exists: {condition_name} ({condition_id})")
        return condition_id

    print(f"📊 Creating condition: {condition_name}...")

    query = """
    mutation($accountId: Int!, $policyId: ID!, $condition: NrqlConditionStaticInput!) {
      alertsNrqlConditionStaticCreate(
        accountId: $accountId
        policyId: $policyId
        condition: $condition
      ) {
        id
        name
      }
    }
    """

    # Remove jira field and prepare condition for GraphQL
    clean_condition = {
        "name": condition_config["name"],
        "enabled": condition_config["enabled"],
        "nrql": condition_config["nrql"],
        "terms": condition_config["terms"],
        "valueFunction": condition_config["valueFunction"],
        "violationTimeLimitSeconds": condition_config["violationTimeLimitSeconds"]
    }

    variables = {
        "accountId": int(NR_ACCOUNT_ID),
        "policyId": policy_id,
        "condition": clean_condition
    }

    result = run_graphql(query, variables)
    condition_id = result["alertsNrqlConditionStaticCreate"]["id"]
    print(f"✅ Created condition: {condition_id}")
    return condition_id


# Alert condition configurations
ALERT_CONDITIONS = [
    {
        "name": "Schedule Manager Failures",
        "jira": "EPLF-73",
        "enabled": True,
        "nrql": {
            "query": "SELECT count(*) FROM Log WHERE message LIKE '%Schedule Manager error%' OR message LIKE '%failed%' FACET entity.name WHERE entity.name = 'epl-schedule-manager-prod'"
        },
        "terms": [{
            "threshold": 0,
            "thresholdOccurrences": "AT_LEAST_ONCE",
            "thresholdDuration": 900,  # 15 minutes in seconds
            "operator": "ABOVE",
            "priority": "CRITICAL"
        }],
        "valueFunction": "SINGLE_VALUE",
        "violationTimeLimitSeconds": 86400  # 24 hours
    },
    {
        "name": "Scheduled Data Fetcher Failures",
        "jira": "EPLF-74",
        "enabled": True,
        "nrql": {
            "query": "SELECT count(*) FROM Log WHERE message LIKE '%Scheduled data fetch%error%' AND entity.name = 'epl-scheduled-fetcher-prod'"
        },
        "terms": [{
            "threshold": 0,
            "thresholdOccurrences": "AT_LEAST_ONCE",
            "thresholdDuration": 900,
            "operator": "ABOVE",
            "priority": "CRITICAL"
        }],
        "valueFunction": "SINGLE_VALUE",
        "violationTimeLimitSeconds": 86400
    },
    {
        "name": "RapidAPI High Error Rate",
        "jira": "EPLF-75",
        "enabled": True,
        "nrql": {
            "query": "SELECT percentage(count(*), WHERE statusCode >= 400) FROM Metric WHERE metricName = 'Custom/RapidAPI/CallMade' AND environment = 'prod'"
        },
        "terms": [{
            "threshold": 10,
            "thresholdOccurrences": "AT_LEAST_ONCE",
            "thresholdDuration": 300,  # 5 minutes
            "operator": "ABOVE",
            "priority": "CRITICAL"
        }],
        "valueFunction": "SINGLE_VALUE",
        "violationTimeLimitSeconds": 86400
    },
    {
        "name": "Stale Data in DynamoDB",
        "jira": "EPLF-76",
        "enabled": True,
        "nrql": {
            "query": "SELECT latest(timestamp) FROM Metric WHERE metricName = 'Custom/RapidAPI/CallMade' AND callReason = 'scheduled_update' AND environment = 'prod'"
        },
        "terms": [{
            "threshold": 46800,  # 13 hours in seconds
            "thresholdOccurrences": "AT_LEAST_ONCE",
            "thresholdDuration": 300,
            "operator": "BELOW",  # Alert if latest timestamp is > 13 hours ago
            "priority": "CRITICAL"
        }],
        "valueFunction": "SINGLE_VALUE",
        "violationTimeLimitSeconds": 86400
    },
    {
        "name": "iOS App Backend Errors",
        "jira": "EPLF-77",
        "enabled": True,
        "nrql": {
            "query": "SELECT count(*) FROM EPLDataFetchError WHERE error != 'network_error'"
        },
        "terms": [{
            "threshold": 100,
            "thresholdOccurrences": "AT_LEAST_ONCE",
            "thresholdDuration": 900,  # 15 minutes
            "operator": "ABOVE",
            "priority": "CRITICAL"
        }],
        "valueFunction": "SINGLE_VALUE",
        "violationTimeLimitSeconds": 86400
    },
    {
        "name": "Position Change Detection Failure",
        "jira": "EPLF-78",
        "enabled": True,
        "nrql": {
            "query": "SELECT count(*) FROM Log WHERE message LIKE '%notification%error%' OR message LIKE '%position change%fail%'"
        },
        "terms": [{
            "threshold": 0,
            "thresholdOccurrences": "AT_LEAST_ONCE",
            "thresholdDuration": 1800,  # 30 minutes
            "operator": "ABOVE",
            "priority": "WARNING"
        }],
        "valueFunction": "SINGLE_VALUE",
        "violationTimeLimitSeconds": 86400
    },
    {
        "name": "API Gateway High Error Rate",
        "jira": "EPLF-79",
        "enabled": True,
        "nrql": {
            "query": "SELECT percentage(count(*), WHERE http.statusCode >= 400) FROM AwsApiGatewayRequest WHERE aws.apigateway.restApiName LIKE '%epl-forecast-prod%'"
        },
        "terms": [{
            "threshold": 10,
            "thresholdOccurrences": "AT_LEAST_ONCE",
            "thresholdDuration": 300,  # 5 minutes
            "operator": "ABOVE",
            "priority": "CRITICAL"
        }],
        "valueFunction": "SINGLE_VALUE",
        "violationTimeLimitSeconds": 86400
    },
    {
        "name": "DynamoDB Write Failures",
        "jira": "EPLF-80",
        "enabled": True,
        "nrql": {
            "query": "SELECT count(*) FROM Log WHERE message LIKE '%DynamoDB%error%' OR message LIKE '%put_item%fail%' OR message LIKE '%store%error%'"
        },
        "terms": [{
            "threshold": 0,
            "thresholdOccurrences": "AT_LEAST_ONCE",
            "thresholdDuration": 900,  # 15 minutes
            "operator": "ABOVE",
            "priority": "CRITICAL"
        }],
        "valueFunction": "SINGLE_VALUE",
        "violationTimeLimitSeconds": 86400
    },
    {
        "name": "ICS Feed Fetch Failures",
        "jira": "EPLF-81",
        "enabled": True,
        "nrql": {
            "query": "SELECT count(*) FROM Log WHERE (message LIKE '%ICS%error%' OR message LIKE '%Could not retrieve cached ICS%' OR message LIKE '%Error parsing ICS%') AND entity.name = 'epl-schedule-manager-prod'"
        },
        "terms": [{
            "threshold": 0,
            "thresholdOccurrences": "AT_LEAST_ONCE",
            "thresholdDuration": 900,  # 15 minutes
            "operator": "ABOVE",
            "priority": "CRITICAL"
        }],
        "valueFunction": "SINGLE_VALUE",
        "violationTimeLimitSeconds": 86400
    },
    {
        "name": "No Telemetry Received",
        "jira": "EPLF-82",
        "enabled": True,
        "nrql": {
            "query": "SELECT count(*) FROM Metric WHERE metricName = 'Custom/RapidAPI/CallMade' AND environment = 'prod'"
        },
        "terms": [{
            "threshold": 1,
            "thresholdOccurrences": "AT_LEAST_ONCE",
            "thresholdDuration": 50400,  # 14 hours
            "operator": "BELOW",
            "priority": "CRITICAL"
        }],
        "valueFunction": "SINGLE_VALUE",
        "violationTimeLimitSeconds": 86400
    },
    {
        "name": "Lambda Unhandled Exceptions",
        "jira": "EPLF-83",
        "enabled": True,
        "nrql": {
            "query": "SELECT count(*) FROM AwsLambdaInvocationError WHERE aws.lambda.functionName LIKE '%epl-%prod'"
        },
        "terms": [{
            "threshold": 5,
            "thresholdOccurrences": "AT_LEAST_ONCE",
            "thresholdDuration": 900,  # 15 minutes
            "operator": "ABOVE",
            "priority": "CRITICAL"
        }],
        "valueFunction": "SINGLE_VALUE",
        "violationTimeLimitSeconds": 86400
    },
    {
        "name": "API Gateway p95 Latency Spike",
        "jira": "EPLF-84",
        "enabled": True,
        "nrql": {
            "query": "SELECT percentile(duration, 95) FROM AwsApiGatewayRequest WHERE aws.apigateway.restApiName LIKE '%epl-forecast-prod%'"
        },
        "terms": [{
            "threshold": 3000,
            "thresholdOccurrences": "AT_LEAST_ONCE",
            "thresholdDuration": 600,  # 10 minutes
            "operator": "ABOVE",
            "priority": "CRITICAL"
        }],
        "valueFunction": "SINGLE_VALUE",
        "violationTimeLimitSeconds": 86400
    },
    {
        "name": "Lambda Dead Letter Queue Messages",
        "jira": "EPLF-60",
        "enabled": True,
        "nrql": {
            "query": "SELECT sum(aws.sqs.ApproximateNumberOfMessagesVisible) FROM QueueSample WHERE provider = 'SqsQueue' AND entityName LIKE '%epl-lambda-errors-prod%'"
        },
        "terms": [{
            "threshold": 0,
            "thresholdOccurrences": "AT_LEAST_ONCE",
            "thresholdDuration": 300,  # 5 minutes
            "operator": "ABOVE",
            "priority": "CRITICAL"
        }],
        "valueFunction": "SINGLE_VALUE",
        "violationTimeLimitSeconds": 86400
    }
]


def main():
    """Main execution"""
    print("\n🚀 EPL Forecast Production Alert Setup\n")
    print(f"Account ID: {NR_ACCOUNT_ID}")
    print(f"Total alert conditions: {len(ALERT_CONDITIONS)}\n")

    try:
        # Step 1: Get or create alert policy
        policy_id = get_or_create_alert_policy()

        # Step 2: Find existing workflow (optional - for reference)
        workflow_id = find_workflow_for_slack()

        # Step 3: Get existing conditions to avoid duplicates
        print("\n🔍 Checking for existing conditions...\n")
        existing_conditions = get_existing_conditions(policy_id)
        print(f"Found {len(existing_conditions)} existing condition(s)")

        # Step 4: Create alert conditions (skip if already exist)
        print("\n📊 Creating alert conditions...\n")
        created_conditions = []

        for condition_config in ALERT_CONDITIONS:
            try:
                condition_id = create_or_skip_condition(policy_id, condition_config, existing_conditions)
                created_conditions.append({
                    "jira": condition_config["jira"],
                    "name": condition_config["name"],
                    "id": condition_id
                })
            except Exception as e:
                print(f"❌ Failed to create {condition_config['name']}: {e}")
                continue

        # Summary
        print(f"\n✅ Alert setup complete!\n")
        print(f"Policy ID: {policy_id}")
        print(f"Workflow ID: {workflow_id}")
        print(f"Conditions created: {len(created_conditions)}/{len(ALERT_CONDITIONS)}\n")

        print("Created conditions:")
        for cond in created_conditions:
            print(f"  {cond['jira']}: {cond['name']} - {cond['id']}")

        # Save results for Jira updates
        with open('/tmp/alert_conditions.json', 'w') as f:
            json.dump({
                "policy_id": policy_id,
                "workflow_id": workflow_id,
                "conditions": created_conditions
            }, f, indent=2)

        print("\n📝 Results saved to /tmp/alert_conditions.json")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
