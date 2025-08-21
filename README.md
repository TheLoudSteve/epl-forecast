# EPL Forecast

An iOS app that shows English Premier League table standings forecasted to 38 games based on current points per game performance.

## Architecture

### Backend (AWS)
- **API Gateway + Lambda**: REST API endpoints
- **DynamoDB**: Caching EPL data with TTL
- **EventBridge**: Scheduled data updates (12am/12pm London time + match-based)
- **S3**: ICS feed caching
- **CloudFormation**: Infrastructure as Code

### iOS App
- **SwiftUI**: Modern iOS interface (iOS 17+)
- **Pull-to-refresh**: Manual data updates
- **Real-time forecasting**: Points per game calculations

## Setup

### Prerequisites
- AWS CLI configured with profiles:
  - `eplprofile-dev` (development account)
  - `eplprofile-prd` (production account)
- RapidAPI key for football-web-pages1 API
- Xcode 15+ for iOS development

### Deployment

#### GitHub Secrets Required
```
AWS_ACCESS_KEY_ID_DEV
AWS_SECRET_ACCESS_KEY_DEV
AWS_ACCESS_KEY_ID_PROD
AWS_SECRET_ACCESS_KEY_PROD
RAPIDAPI_KEY
```

#### Development Environment
Deploys automatically on push to `main` branch:
```bash
git push origin main
```

#### Production Environment
Deploys on GitHub releases:
```bash
git tag v1.0.0
git push origin v1.0.0
# Create release on GitHub
```

### Local Development

#### Backend Testing
```bash
cd backend
pip install -r requirements.txt
pip install pytest pytest-cov moto
python -m pytest tests/ -v --cov=.
```

#### iOS Development
1. Open `ios/EPLForecast/EPLForecast.xcodeproj` in Xcode
2. Update API endpoint in `EPLService.swift`
3. Build and run on simulator or device

## API Endpoints

### GET /health
Health check endpoint
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00Z",
  "service": "epl-forecast-api"
}
```

### GET /table
Forecasted EPL table
```json
{
  "forecast_table": [
    {
      "name": "Arsenal",
      "played": 10,
      "points": 25,
      "points_per_game": 2.5,
      "forecasted_points": 95.0,
      "forecasted_position": 1,
      "current_position": 2
    }
  ],
  "metadata": {
    "last_updated": "2024-01-01T00:00:00Z",
    "total_teams": 20,
    "api_version": "1.0"
  }
}
```

## Data Sources

- **EPL Data**: [football-web-pages1 API](https://rapidapi.com/fluis.lacasse/api/football-web-pages1)
- **Match Schedule**: [ecal.com ICS feed](https://ics.ecal.com/ecal-sub/68a47e3ff49aba000867f867/English%20Premier%20League.ics)

## Monitoring

- CloudWatch Dashboard with metrics for all services
- Automated alerts for errors and performance issues
- Log retention: 7 days (dev), 30 days (prod)

## Cost Optimization

- Lambda functions run only when needed
- DynamoDB on-demand pricing
- API Gateway with caching
- Single-region deployment

## Future Enhancements

- Banner advertisements
- Monthly subscription to remove ads
- Historical forecasting data
- Push notifications for major changes

## License

MIT License