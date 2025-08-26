import UIKit
import NewRelic

class AppDelegate: NSObject, UIApplicationDelegate {
    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey : Any]? = nil) -> Bool {
        
        // Initialize New Relic monitoring
        // TODO: Replace with actual New Relic application token
        NewRelic.start(withApplicationToken: "551fdf56490f49d74c6bbafb22750520FFFFNRAL")
        
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
            "timestamp": Date().timeIntervalSince1970
        ])
    }
    
    func applicationDidEnterBackground(_ application: UIApplication) {
        // Track app going to background
        NewRelic.recordCustomEvent("AppBackground", attributes: [
            "timestamp": Date().timeIntervalSince1970
        ])
    }
}
