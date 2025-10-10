#!/bin/bash
set -e

# EPL Forecast Web App - Manual Deployment Script
# This script deploys the web app to AWS S3 + CloudFront

ENVIRONMENT="${1:-prod}"
REGION="us-west-2"
STACK_NAME="epl-forecast-web-${ENVIRONMENT}"

# Color output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}EPL Forecast Web App Deployment${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo -e "${YELLOW}Environment:${NC} ${ENVIRONMENT}"
echo -e "${YELLOW}Region:${NC} ${REGION}"
echo ""

# Set AWS profile based on environment
if [ "$ENVIRONMENT" == "prod" ]; then
    export AWS_PROFILE=eplprofile-prd
else
    export AWS_PROFILE=eplprofile-dev
fi

echo -e "${GREEN}Step 1: Deploying CloudFormation infrastructure...${NC}"
aws cloudformation deploy \
    --template-file ../infrastructure/web-hosting.yaml \
    --stack-name "$STACK_NAME" \
    --parameter-overrides \
        Environment="$ENVIRONMENT" \
    --capabilities CAPABILITY_IAM \
    --region "$REGION" \
    --no-fail-on-empty-changeset

echo ""
echo -e "${GREEN}Step 2: Getting stack outputs...${NC}"

BUCKET_NAME=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`BucketName`].OutputValue' \
    --output text)

DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`DistributionId`].OutputValue' \
    --output text)

WEBSITE_URL=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`WebsiteURL`].OutputValue' \
    --output text)

echo -e "${YELLOW}Bucket:${NC} $BUCKET_NAME"
echo -e "${YELLOW}Distribution:${NC} $DISTRIBUTION_ID"
echo -e "${YELLOW}URL:${NC} $WEBSITE_URL"
echo ""

echo -e "${GREEN}Step 3: Syncing web files to S3...${NC}"
aws s3 sync . "s3://$BUCKET_NAME/" \
    --exclude "*.md" \
    --exclude ".gitignore" \
    --exclude "vercel.json" \
    --exclude "deploy.sh" \
    --delete \
    --cache-control "public, max-age=300, s-maxage=300" \
    --region "$REGION"

echo ""
echo -e "${GREEN}Step 4: Setting correct content types...${NC}"

# HTML files
aws s3 cp "s3://$BUCKET_NAME/index.html" \
    "s3://$BUCKET_NAME/index.html" \
    --content-type "text/html; charset=utf-8" \
    --metadata-directive REPLACE \
    --cache-control "public, max-age=300, s-maxage=300" \
    --region "$REGION"

# CSS files
aws s3 cp "s3://$BUCKET_NAME/styles.css" \
    "s3://$BUCKET_NAME/styles.css" \
    --content-type "text/css; charset=utf-8" \
    --metadata-directive REPLACE \
    --cache-control "public, max-age=86400, s-maxage=86400" \
    --region "$REGION"

# JS files
aws s3 cp "s3://$BUCKET_NAME/app.js" \
    "s3://$BUCKET_NAME/app.js" \
    --content-type "application/javascript; charset=utf-8" \
    --metadata-directive REPLACE \
    --cache-control "public, max-age=86400, s-maxage=86400" \
    --region "$REGION"

echo ""
echo -e "${GREEN}Step 5: Invalidating CloudFront cache...${NC}"
aws cloudfront create-invalidation \
    --distribution-id "$DISTRIBUTION_ID" \
    --paths "/*" \
    --region "$REGION"

echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${GREEN}✅ Deployment successful!${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo -e "${GREEN}🌐 Website URL:${NC} ${WEBSITE_URL}"
echo ""
echo -e "${YELLOW}Note:${NC} CloudFront distribution may take 5-10 minutes to fully propagate changes."
echo ""
