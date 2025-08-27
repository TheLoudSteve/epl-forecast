# EPL Forecast - Claude Context File

This file contains important context and configuration details for the EPL Forecast project to maintain continuity between Claude Code sessions.

## Project Overview

EPL Forecast is an iOS app with AWS backend that provides English Premier League table forecasts based on current points per game. The app was initially rejected from the App Store due to backend data availability issues, which led to a comprehensive infrastructure overhaul and monitoring implementation.

## Architecture Overview

### Frontend
- **iOS App**: SwiftUI-based EPL forecast viewer
- **Location**: `ios/EPLForecast/`
- **Key Files**: 
  - `EPLForecast/EPLService.swift` - API client with New Relic monitoring
  - `EPLForecast/AppDelegate.swift` - New Relic iOS SDK initialization

### Backend Architecture
- **API Gateway**: REST API v1 with CORS enabled
- **Lambda Functions**: 
  - `scheduled_data_fetcher.py` - Runs 2x daily (00:00/12:00 UTC) 
  - `live_match_fetcher.py` - Runs every 2 minutes in prod, only calls API during matches
  - `api_handler.py` - Handles /health, /table, /debug endpoints
- **DynamoDB**: Stores forecast data with TTL
- **S3**: Caches EPL fixture ICS feeds
- **EventBridge**: Triggers Lambda functions on schedule

### Data Sources
- **RapidAPI**: Football Web Pages API for EPL table data
- **ICS Feed**: EPL fixtures from ics.ecal.com for live match detection

## AWS Account Configuration

### Environments
- **Dev Account**: 738138308534 (us-east-1)
  - Profile: `eplprofile-dev`  
  - Stack: `epl-forecast-dev`
- **Prod Account**: 832199678722 (us-west-2)
  - Profile: `eplprofile-prd`
  - Stack: `epl-forecast-prod`

### Key Infrastructure
- **CloudFormation Template**: `infrastructure/step6.yaml`
- **Dev API**: https://1e4u1ghr3i.execute-api.us-east-1.amazonaws.com/dev
- **Prod API**: TBD (deployed via GitHub Actions)

## Lambda Function Architecture Changes (Recent)

### Previous Architecture (Problem)
- Single `data_fetcher.py` function
- EventBridge triggered every 2 minutes in prod
- Faulty time logic caused 30 RapidAPI calls/hour (should have been 2/day)
- Cost: ~720 calls/day vs expected 2-4 calls/day

### New Architecture (Current)
- **scheduled_data_fetcher.py**: 
  - Runs at 00:00 and 12:00 UTC via cron
  - Prevents data staleness from DynamoDB TTL expiration
  - Always calls RapidAPI (no time checks)
- **live_match_fetcher.py**:
  - Runs every 2 minutes in production only
  - Only calls RapidAPI if live matches detected (15min before to 30min after match)
  - Uses ICS feed parsing for match detection
- **Expected Usage**: 2 calls/day (dev), 2-8 calls/match day (prod)

## New Relic Integration

### Status: ✅ Fully Implemented
- **iOS SDK**: v7.5.9+ with comprehensive event tracking
- **Lambda SDK**: Python agent with custom metrics
- **CloudWatch Metric Streams**: Real-time AWS service metrics
- **Custom RapidAPI Metrics**: Detailed usage tracking

### Keys & Configuration
- **Account ID**: Set in `NEW_RELIC_ACCOUNT_ID` GitHub secret
- **License Key**: Set in `NEW_RELIC_LICENSE_KEY` GitHub secret  
- **Ingest Key**: Set in `NEW_RELIC_INGEST_KEY` GitHub secret
- **iOS Token**: 551fdf56490f49d74c6bbafb22750520FFFFNRAL

### Custom Metrics Implemented
- `Custom/RapidAPI/CallMade` - Total API calls
- `Custom/RapidAPI/LiveMatchCall` - Live match calls
- `Custom/RapidAPI/CallSkipped` - Skipped calls
- `Custom/RapidAPI/ResponseTime` - API response times  
- `Custom/RapidAPI/StatusCode/{code}` - HTTP status tracking
- Custom attributes: call_reason, environment, match_context

## GitHub Actions Workflows

### Deployment Pipelines
- **dev**: `.github/workflows/deploy-dev.yml`
  - Triggers: Push to main branch
  - Deploys: scheduled_data_fetcher + api_handler only
  - Tests: Basic integration tests
- **prod**: `.github/workflows/deploy-prod.yml`
  - Triggers: Manual workflow_dispatch or releases
  - Deploys: Both scheduled + live_match_fetcher functions
  - Tests: Full integration suite

### Required Secrets
- `AWS_ACCESS_KEY_ID_DEV` / `AWS_SECRET_ACCESS_KEY_DEV`
- `AWS_ACCESS_KEY_ID_PROD` / `AWS_SECRET_ACCESS_KEY_PROD`
- `RAPIDAPI_KEY`
- `NEW_RELIC_ACCOUNT_ID`
- `NEW_RELIC_LICENSE_KEY`  
- `NEW_RELIC_INGEST_KEY`

## Common Commands

### AWS CLI Setup
```bash
# Configure profiles (already set up)
aws configure --profile eplprofile-dev
aws configure --profile eplprofile-prd

# Use profiles
export AWS_PROFILE=eplprofile-dev  # or eplprofile-prd
```

### Testing Lambda Functions
```bash
# Test scheduled fetcher
aws lambda invoke --function-name epl-scheduled-fetcher-dev --payload '{}' response.json

# Test live match fetcher (prod only)
aws lambda invoke --function-name epl-live-fetcher-prod --payload '{}' response.json

# Test API handler
curl https://1e4u1ghr3i.execute-api.us-east-1.amazonaws.com/dev/health
curl https://1e4u1ghr3i.execute-api.us-east-1.amazonaws.com/dev/table
```

### GitHub Actions
```bash
# Trigger prod deployment
gh workflow run deploy-prod.yml --ref main

# View recent runs
gh run list --limit 5

# View failed run logs
gh run view <run-id> --log-failed
```

## Key Dates & Context

### App Store Rejection (August 2024)
- **Issue**: "Unable to load data" on iPad Air 5th generation, iPadOS 18.6.2
- **Root Cause**: Backend data not available due to Lambda scheduling issues
- **Resolution**: Complete backend architecture overhaul + monitoring

### Infrastructure Evolution
1. **Initial**: Simple Lambda + API Gateway
2. **v1.0**: Added DynamoDB caching + S3 fixture storage
3. **v1.1**: Fixed region mismatch issues (us-east-1 vs us-west-2)  
4. **v1.2**: Added New Relic monitoring (iOS + Lambda)
5. **v1.3**: Split into scheduled vs live match functions
6. **v1.4**: Added CloudWatch Metric Streams integration

## Known Issues & Solutions

### Previous Issues (Resolved)
- ✅ **Lambda time logic bug**: Fixed with separate function architecture
- ✅ **New Relic layer permissions**: Switched to SDK-based approach
- ✅ **Region mismatch**: Fixed CloudFormation region parameters
- ✅ **Excessive RapidAPI calls**: New architecture limits to match windows only

### Current Monitoring Gaps
- ⏳ **API Gateway detailed metrics**: Need v1 polling integration for resource-level data
- ⏳ **New Relic alerts**: Need error rate and performance thresholds  
- ⏳ **Cost dashboards**: RapidAPI usage tracking and alerting

## File Structure

```
epl-forecast/
├── CLAUDE.md                          # This file
├── ios/EPLForecast/                    # iOS app
├── backend/
│   ├── scheduled_data_fetcher.py       # 2x daily updates
│   ├── live_match_fetcher.py          # Live match monitoring
│   ├── api_handler.py                 # API Gateway endpoints
│   └── requirements.txt               # Python dependencies
├── infrastructure/
│   └── step6.yaml                     # CloudFormation template
└── .github/workflows/                 # CI/CD pipelines
    ├── deploy-dev.yml
    └── deploy-prod.yml
```

## Next Steps / TODO

See active todo list via TodoWrite tool. Key remaining items:
- Test new function architecture end-to-end
- Set up New Relic dashboards for monitoring
- Configure alerts for critical errors
- Validate RapidAPI usage reduction

---

**Last Updated**: August 27, 2025
**Current Session Context**: New Relic CloudWatch Metric Streams deployments in progress