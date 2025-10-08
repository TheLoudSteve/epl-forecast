# New Relic Alerts for EPL Forecast

## Overview
This directory contains configuration and scripts to set up comprehensive monitoring alerts for the EPL Forecast application across both AWS infrastructure and iOS mobile app.

## Alert Policies

### 1. Critical Production Alerts
- **Lambda Function Errors**: Triggers on 5+ errors in 5 minutes
- **RapidAPI Failures**: Triggers on 3+ API failures in 10 minutes  
- **High Lambda Duration**: Triggers when functions exceed 25s (critical) or 15s (warning)
- **iOS App Crashes**: Triggers on crash rate above 5% (critical) or 2% (warning)

### 2. Performance Monitoring
- **Scheduled Fetcher Success Rate**: Alerts when success rate drops below 80% (critical) or 90% (warning)
- **API Gateway 5XX Errors**: Triggers on 10+ server errors in 10 minutes
- **iOS App Load Time**: Alerts when app load time exceeds 8s (critical) or 5s (warning)

## Setup Instructions

### Prerequisites
1. New Relic User API Key with admin permissions
2. Account ID: 7052187 (already configured)
3. Email address for notifications

### Environment Variables
```bash
export NEW_RELIC_USER_API_KEY="your-user-api-key-here"
export NEW_RELIC_ACCOUNT_ID="7052187"  
export NOTIFICATION_EMAIL="your-email@domain.com"
```

### Run Setup Script
```bash
cd monitoring
python3 -m venv venv
source venv/bin/activate
pip install requests
python3 setup-alerts.py
```

## Manual Configuration Required

Some alert conditions require manual setup in the New Relic UI:

### Mobile App Conditions
1. Go to New Relic Alerts & AI > Alert Policies
2. Find "EPL Forecast - Critical Production Alerts" policy
3. Add mobile crash rate condition:
   - Type: Mobile > Crash rate
   - Target: EPL Forecast iOS app
   - Critical: Above 5% for 15 minutes
   - Warning: Above 2% for 10 minutes

4. Add mobile app load time condition:
   - Type: Mobile > App load time
   - Target: EPL Forecast iOS app  
   - Critical: Above 8 seconds for 10 minutes
   - Warning: Above 5 seconds for 5 minutes

## Notification Channels

The setup script creates an email notification channel. You can add additional channels:

- **Slack**: Connect to #alerts channel
- **PagerDuty**: For critical production issues
- **SMS**: For immediate critical alerts

## Custom Metrics Being Monitored

### Lambda Functions
- `Custom/RapidAPI/CallMade` - Total API calls
- `Custom/RapidAPI/Success` - Successful API responses
- `Custom/RapidAPI/Error` - Failed API responses
- `Custom/RapidAPI/ResponseTime` - API response latency

### iOS App (via New Relic Mobile)
- App launch events with version tracking
- Foreground/background transitions
- Crash reporting with stack traces
- Network request monitoring

## Testing Alerts

### Lambda Errors
```bash
# Trigger a test error in the Lambda function
aws lambda invoke \
  --function-name epl-scheduled-fetcher-prod \
  --payload '{"test_error": true}' \
  response.json
```

### API Gateway Errors
```bash  
# Test API endpoint with invalid parameters
curl -X GET "https://your-api-endpoint/invalid-path"
```

## Manual Steps After Setup

### Associate Notification Channels
The setup script creates policies and channels but may not associate them automatically. To connect them:

1. Go to [New Relic Alerts & AI](https://one.newrelic.com/alerts-ai/policies)
2. Select "EPL Forecast - Critical Production Alerts" 
3. Click "Add notification channels"
4. Select "EPL Forecast Email Alerts" channel
5. Repeat for "EPL Forecast - Performance Monitoring" policy

### Dashboard Setup

### Create Production Overview Dashboard
```bash
cd monitoring
source venv/bin/activate
python3 create-dashboard.py
```

This creates a comprehensive dashboard with:
- **System Health**: Lambda success rates, API call metrics, error counts
- **AWS Infrastructure**: Function performance, API Gateway metrics, S3 storage
- **Custom Metrics**: RapidAPI usage trends, response times, match detection
- **Mobile Analytics**: App launches, crashes, performance metrics

## Alert Policy URLs
- https://one.newrelic.com/alerts-ai/policies (Account: 7052187)
- https://one.newrelic.com/dashboards (Account: 7052187)

## Dashboard Management

### Repeatable Dashboard Updates

Use the `manage_dashboard.py` script to programmatically update dashboards:

#### Setup
```bash
# Get your New Relic User API Key from:
# https://one.newrelic.com/admin-portal/api-keys/home
export NEW_RELIC_API_KEY=NRAK-YOUR-KEY-HERE
pip install requests
```

#### Export Existing Dashboard
```bash
python3 manage_dashboard.py export <dashboard-guid>
```

Find the GUID from the dashboard URL: `https://one.newrelic.com/dashboards/<GUID>`

#### Update Dashboard from JSON
```bash
python3 manage_dashboard.py update <dashboard-guid> new-relic-dashboard.json
```

#### Create New Dashboard
```bash
python3 manage_dashboard.py create new-relic-dashboard.json
```

### Dashboard Structure

The `new-relic-dashboard.json` contains:
- **3 Pages**: Football API Overview, Business Metrics, System Performance
- **Time Window Variable**: Dropdown with 6h/12h/24h/48h/7d/30d options
- **All widgets** use `{{timeWindow}}` variable for consistent filtering

### Workflow for Dashboard Changes

1. **Edit** `new-relic-dashboard.json`

2. **Convert and create/update** dashboard:
   ```bash
   cd monitoring
   source venv/bin/activate
   export NEW_RELIC_API_KEY=your-key

   # Convert to API-compatible format (removes variables, converts time)
   python3 convert_dashboard.py new-relic-dashboard.json

   # Fix metric names
   python3 << 'EOF'
   import json
   with open('dashboard-converted.json') as f:
       d = json.load(f)
   def replace(obj):
       if isinstance(obj, dict):
           if 'query' in obj and isinstance(obj['query'], str):
               obj['query'] = obj['query'].replace('{{timeWindow}}', '1 day ago')
               obj['query'] = obj['query'].replace('aws.apigateway.4XXError', '`aws.apigateway.4XXError`')
               obj['query'] = obj['query'].replace('aws.apigateway.5XXError', '`aws.apigateway.5XXError`')
           return {k: replace(v) for k, v in obj.items()}
       elif isinstance(obj, list):
           return [replace(i) for i in obj]
       return obj
   d = replace(d)
   with open('dashboard-fixed.json', 'w') as f:
       json.dump(d, f, indent=2)
   EOF

   # Create or update
   python3 manage_dashboard.py sync dashboard-fixed.json
   ```

3. **Add time window variable manually** (one-time setup):
   - Open dashboard in New Relic UI
   - Click "..." menu → "Edit"
   - Click "Variables" → "+ Add variable"
   - Name: `timeWindow`
   - Type: `List of values`
   - Add values: `6 hours ago`, `12 hours ago`, `1 day ago` (default), `2 days ago`, `7 days ago`, `30 days ago`
   - Save

4. **Commit changes**:
   ```bash
   git add new-relic-dashboard.json
   git commit -m "Update dashboard: <description>"
   ```

## Troubleshooting

### Common Issues
1. **API Key Permissions**: Ensure User API Key has "Alerts" and "Dashboard" permissions
2. **Account Access**: Verify account ID 7052187 is accessible with your API key
3. **Email Delivery**: Check spam folder for New Relic alert emails
4. **Unknown field errors**: Export dashboard first to see correct format

### Logs and Debugging
The setup script provides detailed output for troubleshooting. Common errors:
- 403 Forbidden: API key lacks permissions
- 404 Not Found: Incorrect account ID or resource doesn't exist
- 400 Bad Request: Invalid query syntax or configuration