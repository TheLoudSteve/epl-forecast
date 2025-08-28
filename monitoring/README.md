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

## Troubleshooting

### Common Issues
1. **API Key Permissions**: Ensure User API Key has "Alerts" permissions
2. **Account Access**: Verify account ID 7052187 is accessible with your API key
3. **Email Delivery**: Check spam folder for New Relic alert emails

### Logs and Debugging
The setup script provides detailed output for troubleshooting. Common errors:
- 403 Forbidden: API key lacks permissions
- 404 Not Found: Incorrect account ID or resource doesn't exist
- 400 Bad Request: Invalid query syntax or configuration