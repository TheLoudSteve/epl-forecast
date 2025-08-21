# IAM Setup for GitHub Actions

This directory contains the IAM policy required for GitHub Actions to deploy the EPL Forecast application.

## Setup Instructions

### 1. Create IAM Users

Create two IAM users in your AWS accounts:

**Development Account:**
```bash
aws iam create-user --user-name github-actions-epl-dev --profile eplprofile-dev
```

**Production Account:**
```bash
aws iam create-user --user-name github-actions-epl-prod --profile eplprofile-prd
```

### 2. Create and Attach Policy

**Development Account:**
```bash
aws iam create-policy \
  --policy-name GitHubActionsEPLPolicy \
  --policy-document file://iam/github-actions-policy.json \
  --profile eplprofile-dev

aws iam attach-user-policy \
  --user-name github-actions-epl-dev \
  --policy-arn arn:aws:iam::YOUR-DEV-ACCOUNT-ID:policy/GitHubActionsEPLPolicy \
  --profile eplprofile-dev
```

**Production Account:**
```bash
aws iam create-policy \
  --policy-name GitHubActionsEPLPolicy \
  --policy-document file://iam/github-actions-policy.json \
  --profile eplprofile-prd

aws iam attach-user-policy \
  --user-name github-actions-epl-prod \
  --policy-arn arn:aws:iam::YOUR-PROD-ACCOUNT-ID:policy/GitHubActionsEPLPolicy \
  --profile eplprofile-prd
```

### 3. Create Access Keys

**Development Account:**
```bash
aws iam create-access-key --user-name github-actions-epl-dev --profile eplprofile-dev
```

**Production Account:**
```bash
aws iam create-access-key --user-name github-actions-epl-prod --profile eplprofile-prd
```

### 4. Add GitHub Secrets

Add the following secrets to your GitHub repository (Settings → Secrets and variables → Actions):

- `AWS_ACCESS_KEY_ID_DEV` - Access key ID from dev account
- `AWS_SECRET_ACCESS_KEY_DEV` - Secret access key from dev account
- `AWS_ACCESS_KEY_ID_PROD` - Access key ID from prod account
- `AWS_SECRET_ACCESS_KEY_PROD` - Secret access key from prod account
- `RAPIDAPI_KEY` - Your RapidAPI key for football-web-pages1

## Policy Details

The policy grants minimal required permissions for:

- **CloudFormation**: Deploy and manage stacks
- **IAM**: Create and manage service roles
- **Lambda**: Create and update functions
- **DynamoDB**: Create and manage tables
- **S3**: Create and manage buckets
- **API Gateway**: Create and manage REST APIs
- **EventBridge**: Create and manage rules
- **CloudWatch**: Create logs, dashboards, and alarms
- **SNS**: Create topics for alerting

All permissions are scoped to resources with the `epl-` prefix for security.

## Security Notes

- All resource permissions are scoped to `epl-*` resources only
- IAM permissions are limited to roles with `epl-` prefix
- No broad administrative permissions are granted
- Follow principle of least privilege