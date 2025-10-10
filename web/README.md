# EPL Forecast Web App

A responsive web application that displays English Premier League table forecasts based on current points per game.

## Features

- **Real-time Data**: Fetches live forecast data from production API
- **Responsive Design**: Works seamlessly on desktop, tablet, and mobile devices
- **Dark Mode Support**: Automatically adapts to system color scheme preferences
- **Auto-refresh**: Updates data every 5 minutes when tab is visible
- **Position Changes**: Visual indicators showing predicted position changes
- **Modern UI**: Clean, Premier League-themed design with smooth animations

## Files

- `index.html` - Main HTML structure
- `styles.css` - Responsive CSS with dark mode support
- `app.js` - JavaScript for API interaction and table rendering

## Local Development

Start a local web server:

```bash
cd web
python3 -m http.server 8000
```

Then open http://localhost:8000 in your browser.

## Deployment Options

### Option 1: AWS S3 + CloudFront (Recommended - Automated)

**Advantages:**
- Low cost (~$0.50/month)
- Global CDN distribution with edge locations
- HTTPS by default with HTTP/2 and HTTP/3 support
- Integrates with existing AWS infrastructure
- Automatic cache invalidation
- Security headers and compression enabled
- Origin Access Control (OAC) for secure S3 access

**Automated Deployment (GitHub Actions):**

The web app automatically deploys to production when changes are pushed to the `web/` directory:

```bash
git add web/
git commit -m "Update web app"
git push
```

Or trigger manual deployment:

```bash
gh workflow run deploy-web.yml
```

**Manual Deployment:**

```bash
cd web
./deploy.sh prod  # or 'dev' for development
```

The deployment script will:
1. Deploy CloudFormation infrastructure (S3 + CloudFront)
2. Sync web files to S3 bucket
3. Set correct content types and cache headers
4. Invalidate CloudFront cache for immediate updates

**Infrastructure Details:**
- **CloudFormation Template:** `infrastructure/web-hosting.yaml`
- **S3 Bucket:** Private with CloudFront OAC access only
- **Cache Policy:** 5 minutes for HTML, 24 hours for CSS/JS
- **Security Headers:** HSTS, X-Content-Type-Options, X-Frame-Options, etc.
- **Error Handling:** 403/404 errors redirect to index.html (SPA support)

**Custom Domain (Optional):**

To use a custom domain, update the CloudFormation parameters:

```bash
aws cloudformation deploy \
    --template-file infrastructure/web-hosting.yaml \
    --stack-name epl-forecast-web-prod \
    --parameter-overrides \
        Environment=prod \
        DomainName=forecast.example.com \
        CertificateArn=arn:aws:acm:us-east-1:ACCOUNT:certificate/CERT_ID
```

Note: ACM certificate must be in us-east-1 region for CloudFront.

### Option 2: Vercel (Easiest)

**Advantages:**
- Free tier available
- Automatic HTTPS
- Git-based deployments
- Zero configuration needed

**Setup:**
1. Install Vercel CLI: `npm i -g vercel`
2. Run `vercel` in the web directory
3. Follow prompts to deploy

### Option 3: Netlify

**Advantages:**
- Free tier with generous limits
- Drag-and-drop deployment
- Automatic HTTPS
- Form handling (if needed later)

**Setup:**
1. Sign up at netlify.com
2. Drag the `web` folder to Netlify dashboard
3. Site is live immediately

### Option 4: GitHub Pages

**Advantages:**
- Completely free
- Integrates with GitHub repo
- Simple setup

**Setup:**
1. Create `docs` folder in repo root
2. Copy web files to `docs/`
3. Enable GitHub Pages in repo settings
4. Point to `docs` folder

## API Endpoint

Production API: `https://aiighxj72l.execute-api.us-west-2.amazonaws.com/prod/table`

Returns JSON:
```json
{
  "teams": [
    {
      "name": "Arsenal",
      "current_position": 2,
      "forecasted_position": 1,
      "played": 10,
      "points": 23,
      "points_per_game": 2.3,
      "goal_difference": 10,
      "forecasted_points": 87.4
    }
  ],
  "last_updated": "2025-10-08T00:00:00Z",
  "total_teams": 20
}
```

## Browser Compatibility

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Mobile browsers (iOS Safari, Chrome Mobile)

## Future Enhancements

- Historical data charts
- Team-specific pages with statistics
- Social sharing functionality
- Notification system for position changes
- Progressive Web App (PWA) support
- Match schedule integration
