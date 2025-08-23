# Production Setup Guide

## Required GitHub Secrets

Add these secrets to your GitHub repository under Settings > Secrets and variables > Actions:

### Production AWS Credentials
- `AWS_ACCESS_KEY_ID_PROD` - Production AWS Access Key ID
- `AWS_SECRET_ACCESS_KEY_PROD` - Production AWS Secret Access Key

### Shared API Key
- `RAPIDAPI_KEY` - Your RapidAPI key (used for both dev and prod)

## Production Environment

- **AWS Account ID**: `832199678722`
- **Stack Name**: `epl-forecast-prod`
- **AWS Region**: `us-east-1`
- **Trigger**: Releases (when you publish a GitHub release)

## Deployment Process

1. **Automated Testing**: Runs all backend tests
2. **Infrastructure Deployment**: Deploys CloudFormation stack with production resources
3. **Integration Testing**: Tests health and table endpoints
4. **Monitoring**: Provides production API endpoint URL

## Production Resources Created

- DynamoDB Table: `epl-forecast-data-prod`
- Lambda Functions: 
  - `EPLDataFetcher-prod`
  - `EPLAPIHandler-prod`
- API Gateway: Production REST API
- EventBridge: Scheduled data updates (every 4 hours)
- S3 Bucket: For caching feeds
- IAM Roles: Function execution roles

## Monitoring Production

- **Health Check**: `https://{api-endpoint}/health`
- **Data Endpoint**: `https://{api-endpoint}/table`
- **CloudWatch**: Logs and metrics available in AWS Console
- **DynamoDB**: Data cached with TTL for performance

## Security

- Production uses separate AWS credentials
- All resources are properly tagged with Environment=prod
- API includes CORS headers for web app integration

## Release Process

1. Create a GitHub release from the main branch
2. Workflow automatically deploys to production
3. Integration tests verify deployment
4. Production API endpoint is provided in workflow output

## iOS App Configuration

Update your iOS app's EPLService to use the production endpoint:

```swift
private let baseURL = "https://your-prod-api-endpoint.com"
```