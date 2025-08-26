# New Relic iOS Integration Setup

## Overview
This document outlines the New Relic monitoring integration for the EPL Forecast iOS app, providing comprehensive observability for crashes, performance, and user experience.

## ✅ What's Implemented

### 📱 App Lifecycle Monitoring
- **App Launch Tracking**: Records app launches with version/build info
- **Foreground/Background Events**: Tracks app state changes
- **Crash Reporting**: Automatic crash detection with stack traces

### 🌐 Network Monitoring  
- **API Request Tracking**: Monitors all EPL data fetch requests
- **Response Time Metrics**: Measures API performance in milliseconds
- **Error Classification**: Categorizes network, HTTP, and parsing errors
- **Success Metrics**: Tracks successful data fetches with team counts

### 🖥️ UI Performance
- **Table View Monitoring**: Tracks when main forecast table appears
- **User Interactions**: Records pull-to-refresh actions
- **Custom Events**: EPL-specific events like data loading states

## 🔧 Files Modified

### Core App Files
- `AppDelegate.swift` - New Relic initialization and lifecycle monitoring
- `EPLForecastApp.swift` - Added AppDelegate adapter for SwiftUI
- `EPLService.swift` - Comprehensive API monitoring with custom events
- `TableView.swift` - UI interaction and performance monitoring

### Dependencies
- `Package.swift` - Swift Package Manager configuration for New Relic SDK

## 📊 Custom Events Tracked

### Network Events
- `EPLDataFetchStart` - When API request begins
- `EPLDataFetchSuccess` - Successful API responses with metrics
- `EPLDataFetchError` - All types of API errors with classification

### App Events  
- `AppLaunch` - App startup with version info
- `AppForeground`/`AppBackground` - App state transitions
- `TableViewAppeared` - Main screen load
- `UserRefresh` - Pull-to-refresh actions

## 🚀 Setup Instructions

### 1. New Relic Account Setup
1. Create New Relic account at https://newrelic.com
2. Navigate to Mobile monitoring
3. Create new iOS application
4. Copy the application token

### 2. Configure App Token
1. Open `AppDelegate.swift`
2. Replace `"YOUR_NEW_RELIC_APP_TOKEN"` with your actual token
3. **Security Note**: Consider using environment variables or secure storage

### 3. Xcode Project Setup
The New Relic iOS agent will be added via Swift Package Manager:
1. Open Xcode project
2. File → Add Package Dependencies
3. Enter: `https://github.com/newrelic/newrelic-ios-agent-spm`
4. Select version 7.0.0 or later
5. Add to your main app target

### 4. Build and Test
1. Build the project (may need to refresh Package Dependencies)
2. Run on device/simulator
3. Check New Relic dashboard for incoming data

## 📈 Expected Benefits

### For App Store Submission
- **Crash Prevention**: Immediate notification of crashes during review
- **Performance Insights**: Response time monitoring for "Unable to load data" issues
- **Device-Specific Issues**: Track iPad vs iPhone performance differences

### For Production Monitoring
- **Real-Time Alerts**: Get notified when API errors spike
- **User Experience**: Monitor app performance across different devices
- **EPL Data Quality**: Track successful vs failed forecast updates

## 🛠️ Troubleshooting

### Build Issues
- Ensure Xcode 15+ for New Relic SDK 7.0+
- Clean build folder if Package dependencies fail
- Verify minimum iOS deployment target (iOS 12+)

### No Data Appearing
- Check application token is correct
- Verify app has internet connection
- Allow 5-10 minutes for initial data to appear in New Relic

### SwiftUI Integration
- AppDelegate is required for New Relic initialization
- Uses `@UIApplicationDelegateAdaptor` for SwiftUI compatibility
- All monitoring works seamlessly with SwiftUI views

## 🔍 Next Steps
1. Set up New Relic account and obtain app token
2. Configure Xcode project with New Relic dependency  
3. Test monitoring in development
4. Create production dashboards and alerts
5. Monitor App Store submission process

This integration provides comprehensive visibility into your iOS app performance, helping ensure successful App Store submission and production monitoring.