# EPL Forecast - GitHub Actions Workflows

This directory contains the CI/CD workflows for deploying the EPL Forecast application to development and production environments.

## Workflows Overview

### 1. Development Deployment (`deploy-dev.yml`)

**Triggers:**
- Push to `main` branch
- Pull requests to `main` branch

**Environment:** Development (us-east-1)

**Process:**
1. **Test Phase**: Run backend tests with coverage reporting
2. **Infrastructure**: Deploy CloudFormation stack to development
3. **Lambda Deployment**: Package and update Lambda function code directly
4. **Integration**: Trigger initial data fetch and verify endpoints

**Required Secrets:**
- `AWS_ACCESS_KEY_ID_DEV`
- `AWS_SECRET_ACCESS_KEY_DEV` 
- `RAPIDAPI_KEY`

### 2. Production Deployment (`deploy-prod.yml`)

**Triggers:**
- GitHub releases (published)
- Manual workflow dispatch

**Environment:** Production (us-west-2, account: 832199678722)

**Process:**
1. **Package**: Create Lambda deployment packages with dependencies
2. **Upload**: Store packages in S3 deployment bucket
3. **Infrastructure**: Deploy CloudFormation stack to production
4. **Lambda Update**: Update Lambda functions from S3 packages
5. **Integration Tests**: Verify health and table endpoints

**Required Secrets:**
- `AWS_ACCESS_KEY_ID_PROD`
- `AWS_SECRET_ACCESS_KEY_PROD`
- `RAPIDAPI_KEY` (shared with dev)

## Environment Configuration

### Development
- **Region**: us-east-1
- **Stack Name**: epl-forecast-dev
- **Trigger**: Automatic on main branch changes
- **Lambda Deployment**: Direct ZIP upload
- **Testing**: Full test suite with coverage

### Production  
- **Region**: us-west-2
- **Stack Name**: epl-forecast-prod
- **Trigger**: Manual releases only
- **Lambda Deployment**: S3-based deployment
- **Testing**: Integration tests only

## Deployment Process

### For Development Changes
1. Push changes to `main` branch
2. GitHub Actions automatically:
   - Runs tests
   - Deploys to dev environment
   - Updates Lambda functions
   - Triggers data fetch

### For Production Releases
1. Create a GitHub release from `main` branch
2. GitHub Actions automatically:
   - Packages Lambda functions with dependencies
   - Deploys complete infrastructure to production
   - Runs integration tests
   - Provides production API endpoint

Or run manually:
- Go to Actions tab → "Deploy to Production" → "Run workflow"

## Infrastructure Resources

Both environments create:
- **DynamoDB Table**: `epl-data-{environment}`
- **Lambda Functions**: 
  - `epl-data-fetcher-{environment}`
  - `epl-api-handler-{environment}`
- **API Gateway**: REST API with `/health` and `/table` endpoints
- **S3 Bucket**: For ICS feed caching
- **EventBridge**: Scheduled data updates (every 4 hours)
- **IAM Roles**: Lambda execution permissions

## Troubleshooting

### Common Issues

1. **Stack in ROLLBACK_COMPLETE state**
   - Workflows automatically detect and delete failed stacks
   - Retry the deployment after cleanup

2. **Lambda import errors**
   - Ensure proper packaging with dependencies
   - Production uses S3-based deployment for better reliability

3. **API endpoint not found**
   - Check CloudFormation outputs for `APIEndpoint` key
   - Verify stack deployment completed successfully

4. **Permission errors**
   - Ensure AWS credentials have proper IAM permissions
   - Check that GitHub Secrets are correctly configured

### Manual Deployment

If workflows fail, you can deploy manually:

```bash
# For production (using eplprofile-prd)
aws --profile eplprofile-prd cloudformation deploy \
  --template-file infrastructure/step6.yaml \
  --stack-name epl-forecast-prod \
  --parameter-overrides Environment=prod RapidAPIKey=YOUR_KEY \
  --capabilities CAPABILITY_IAM \
  --region us-west-2
```

## Monitoring

- **GitHub Actions**: Monitor workflow runs in the Actions tab
- **AWS CloudWatch**: Lambda function logs and metrics
- **API Endpoints**: 
  - Dev: Check CloudFormation outputs in us-east-1
  - Prod: Check CloudFormation outputs in us-west-2

## Security

- All secrets are stored in GitHub repository secrets
- Production deployment requires explicit release or manual trigger
- AWS credentials are scoped to specific environments
- RapidAPI key is shared between environments (same data source)