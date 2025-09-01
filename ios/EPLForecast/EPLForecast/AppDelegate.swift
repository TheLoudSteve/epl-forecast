import UIKit
import NewRelic

class AppDelegate: NSObject, UIApplicationDelegate {
    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey : Any]? = nil) -> Bool {
        
        // Initialize New Relic monitoring with proper configuration
        // Configure New Relic before starting
        NewRelic.enableFeatures([
            .NRFeatureFlag_DefaultInteractions,
            .NRFeatureFlag_CrashReporting,
            .NRFeatureFlag_HttpResponseBodyCapture,
            .NRFeatureFlag_NetworkRequestEvents
        ])
        
        // New Relic configuration - replace with your actual values
        let newRelicAccountId = "7052187"
        let newRelicAppToken = "AAaccb50adc4bb8233bf21a764a161017b06d22b80-NRMA"
        
        // Configure New Relic with account ID for distributed tracing
        NewRelic.setUserId("epl-forecast-ios")
        
        // Start New Relic with application token
        NewRelic.start(withApplicationToken: newRelicAppToken)
        
        print("New Relic initialized successfully with Account ID: \(newRelicAccountId)")
        
        // Record app launch event
        NewRelic.recordCustomEvent("AppLaunch", attributes: [
            "launchTime": Date().timeIntervalSince1970,
            "version": Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "unknown",
            "build": Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "unknown"
        ])
        
        // Enable crash reporting and configure logging
        print("EPL Forecast app launched successfully with New Relic monitoring")
        
        return true
    }
    
    func applicationWillEnterForeground(_ application: UIApplication) {
        // Track app returning to foreground
        NewRelic.recordCustomEvent("AppForeground", attributes: [
            "eventTime": Date().timeIntervalSince1970
        ])
    }
    
    func applicationDidEnterBackground(_ application: UIApplication) {
        // Track app going to background
        NewRelic.recordCustomEvent("AppBackground", attributes: [
            "eventTime": Date().timeIntervalSince1970
        ])
    }
}
