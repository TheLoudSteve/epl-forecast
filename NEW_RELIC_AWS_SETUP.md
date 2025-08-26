# New Relic AWS Lambda Integration Setup

## Overview
This document outlines the New Relic monitoring integration for AWS Lambda functions in the EPL Forecast application.

## ✅ What's Implemented

### 📦 **Lambda Layer Integration**
- **New Relic Python 3.11 Layer** added to both Lambda functions
- **Layer ARN**: `arn:aws:lambda:us-west-2:451483290750:layer:NewRelicPython311:14`
- **Conditional deployment** - only enabled when New Relic account ID is provided

### ⚙️ **Environment Variables**
Each Lambda function automatically gets:
- `NEW_RELIC_ACCOUNT_ID` - Your New Relic account ID
- `NEW_RELIC_LICENSE_KEY` - Your New Relic license key
- `NEW_RELIC_LAMBDA_HANDLER` - Points to original handler (`data_fetcher.lambda_handler` or `api_handler.lambda_handler`)
- `NEW_RELIC_LAMBDA_EXTENSION_ENABLED` - Set to `'true'` to enable extension

### 🎯 **Handler Wrapping**
- **With New Relic**: `newrelic_lambda_wrapper.lambda_handler` (New Relic wrapper)
- **Without New Relic**: Original handlers (`data_fetcher.lambda_handler`, `api_handler.lambda_handler`)

## 🔐 **Required GitHub Secrets**

You need to create exactly **2 GitHub repository secrets**:

### 1. NEW_RELIC_ACCOUNT_ID
- **Value**: Your New Relic account ID (numeric)
- **Location**: Settings → Secrets and variables → Actions → New repository secret
- **Example**: `3625516` (your actual account ID from New Relic)

### 2. NEW_RELIC_LICENSE_KEY  
- **Value**: Your New Relic license key
- **Location**: Settings → Secrets and variables → Actions → New repository secret
- **Example**: `abc123def456...` (40+ character license key from New Relic)

## 📋 **How to Find Your New Relic Credentials**

### Account ID:
1. Log into New Relic
2. Click your user menu (bottom left)
3. Click "Administration"
4. Your Account ID is displayed at the top

### License Key:
1. Go to New Relic → Administration → API Keys
2. Look for "License keys" section
3. Copy your license key (starts with "NRAK-...")

## 🚀 **Deployment Process**

### Automatic Deployment
Both dev and production workflows now include New Relic parameters:

```yaml
# Development (triggered on push to main)
aws cloudformation deploy \
  --parameter-overrides \
    NewRelicAccountId=${{ secrets.NEW_RELIC_ACCOUNT_ID }} \
    NewRelicLicenseKey=${{ secrets.NEW_RELIC_LICENSE_KEY }}

# Production (triggered on GitHub release)
aws cloudformation deploy \
  --parameter-overrides \
    NewRelicAccountId=${{ secrets.NEW_RELIC_ACCOUNT_ID }} \
    NewRelicLicenseKey=${{ secrets.NEW_RELIC_LICENSE_KEY }}
```

### Conditional Monitoring
- **If secrets are set**: New Relic monitoring is enabled automatically
- **If secrets are empty**: Functions deploy normally without monitoring
- **No code changes needed** - handled entirely by CloudFormation

## 📊 **What Gets Monitored**

### Performance Metrics
- **Function duration** and cold start times
- **Memory usage** and timeout tracking
- **Invocation count** and error rates
- **Custom EPL metrics** (data fetch success/failure)

### Error Tracking
- **Exception capture** with full stack traces
- **Error correlation** across Lambda functions
- **API Gateway integration** for distributed tracing

### Distributed Tracing
- **End-to-end tracing** from iOS app → API Gateway → Lambda → DynamoDB
- **Request correlation** across all components
- **Performance bottleneck identification**

## 🔍 **Monitoring Dashboard**

After deployment, you'll see:
- **Lambda functions** in New Relic APM
- **Performance charts** for both functions
- **Error tracking** for EPL data processing
- **Custom events** for business metrics

## 🛠️ **Troubleshooting**

### No Data Appearing
1. Verify GitHub secrets are set correctly
2. Check CloudFormation parameters were passed
3. Confirm Layer ARN is correct for your region
4. Allow 5-10 minutes for data to appear

### Build Failures
- Ensure secrets `NEW_RELIC_ACCOUNT_ID` and `NEW_RELIC_LICENSE_KEY` exist
- Verify license key format (should start with "NRAK-")
- Check account ID is numeric only

### Layer Version Updates
The Layer ARN in `step6.yaml` may need updating:
- Check https://layers.newrelic-external.com/ for latest version
- Update version number in ARN (currently `:14`)

## 🎯 **Next Steps**

1. **Create GitHub secrets** with your New Relic credentials
2. **Deploy via push to main** (dev) or **create GitHub release** (prod)  
3. **Verify monitoring** appears in New Relic dashboard
4. **Set up alerts** for critical errors and performance issues

This integration provides comprehensive Lambda monitoring without any code changes to your functions!