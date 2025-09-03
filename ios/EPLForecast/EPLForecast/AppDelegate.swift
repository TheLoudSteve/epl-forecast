import UIKit
import NewRelic
import UserNotifications

class AppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey : Any]? = nil) -> Bool {
        
        // Initialize New Relic monitoring with proper configuration
        // Configure New Relic before starting
        #if targetEnvironment(simulator)
        // Disable features that cause CoreTelephony warnings in simulator
        NewRelic.enableFeatures([
            .NRFeatureFlag_DefaultInteractions,
            .NRFeatureFlag_HttpResponseBodyCapture,
            .NRFeatureFlag_NetworkRequestEvents
        ])
        #else
        // Full feature set for device builds
        NewRelic.enableFeatures([
            .NRFeatureFlag_DefaultInteractions,
            .NRFeatureFlag_CrashReporting,
            .NRFeatureFlag_HttpResponseBodyCapture,
            .NRFeatureFlag_NetworkRequestEvents
        ])
        #endif
        
        // New Relic configuration - replace with your actual values
        let newRelicAccountId = "7052187"
        let newRelicAppToken = "AAaccb50adc4bb8233bf21a764a161017b06d22b80-NRMA"
        
        // Configure New Relic with account ID for distributed tracing
        NewRelic.setUserId("epl-forecast-ios")
        
        // Start New Relic with application token
        NewRelic.start(withApplicationToken: newRelicAppToken)
        
        print("New Relic initialized successfully with Account ID: \(newRelicAccountId)")
        
        #if targetEnvironment(simulator)
        print("Running in simulator - some New Relic features disabled to avoid CoreTelephony warnings")
        #endif
        
        // Record app launch event
        NewRelic.recordCustomEvent("AppLaunch", attributes: [
            "launchTime": Date().timeIntervalSince1970,
            "version": Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "unknown",
            "build": Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "unknown"
        ])
        
        // Enable crash reporting and configure logging
        print("EPL Forecast app launched successfully with New Relic monitoring")
        
        // Set up push notifications
        setupPushNotifications(application)
        
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
    
    // MARK: - Push Notifications
    
    private func setupPushNotifications(_ application: UIApplication) {
        UNUserNotificationCenter.current().delegate = self
        
        // Request notification permissions
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { granted, error in
            if granted {
                print("Push notification permission granted")
                DispatchQueue.main.async {
                    application.registerForRemoteNotifications()
                }
                
                // Track permission granted
                NewRelic.recordCustomEvent("PushNotificationPermission", attributes: [
                    "granted": true,
                    "eventTime": Date().timeIntervalSince1970
                ])
            } else {
                print("Push notification permission denied: \(error?.localizedDescription ?? "unknown error")")
                
                // Track permission denied
                NewRelic.recordCustomEvent("PushNotificationPermission", attributes: [
                    "granted": false,
                    "error": error?.localizedDescription ?? "unknown",
                    "eventTime": Date().timeIntervalSince1970
                ])
            }
        }
    }
    
    // Handle successful push token registration
    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        let tokenString = deviceToken.map { String(format: "%02.2hhx", $0) }.joined()
        print("APNS token received: \(tokenString)")
        
        // Track token registration
        NewRelic.recordCustomEvent("APNSTokenReceived", attributes: [
            "tokenLength": tokenString.count,
            "eventTime": Date().timeIntervalSince1970
        ])
        
        // Register token with backend
        registerPushTokenWithBackend(tokenString)
    }
    
    // Handle push token registration failure
    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {
        print("Failed to register for push notifications: \(error.localizedDescription)")
        
        // Track token registration failure
        NewRelic.recordCustomEvent("APNSTokenFailed", attributes: [
            "error": error.localizedDescription,
            "eventTime": Date().timeIntervalSince1970
        ])
    }
    
    private func registerPushTokenWithBackend(_ token: String) {
        let baseURL = "https://aiighxj72l.execute-api.us-west-2.amazonaws.com/prod"
        guard let url = URL(string: "\(baseURL)/preferences/register") else {
            print("Invalid backend URL")
            return
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        // Use device identifier as user ID
        let userID = UIDevice.current.identifierForVendor?.uuidString ?? "unknown_device"
        request.setValue(userID, forHTTPHeaderField: "X-User-ID")
        
        let body = ["push_token": token]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        
        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                print("Failed to register push token: \(error.localizedDescription)")
                
                NewRelic.recordCustomEvent("PushTokenRegistrationFailed", attributes: [
                    "error": error.localizedDescription,
                    "userID": userID
                ])
                return
            }
            
            guard let httpResponse = response as? HTTPURLResponse else {
                print("Invalid response when registering push token")
                return
            }
            
            if httpResponse.statusCode == 200 {
                print("Push token registered successfully with backend")
                
                NewRelic.recordCustomEvent("PushTokenRegistrationSuccess", attributes: [
                    "statusCode": httpResponse.statusCode,
                    "userID": userID
                ])
            } else {
                print("Failed to register push token. Status: \(httpResponse.statusCode)")
                
                if let data = data, let responseString = String(data: data, encoding: .utf8) {
                    print("Response: \(responseString)")
                }
                
                NewRelic.recordCustomEvent("PushTokenRegistrationFailed", attributes: [
                    "statusCode": httpResponse.statusCode,
                    "userID": userID
                ])
            }
        }.resume()
    }
    
    // MARK: - UNUserNotificationCenterDelegate
    
    // Handle notification when app is in foreground
    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification, withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        // Show notification even when app is active
        completionHandler([.banner, .sound, .badge])
        
        // Track notification received
        NewRelic.recordCustomEvent("PushNotificationReceived", attributes: [
            "appState": "foreground",
            "title": notification.request.content.title,
            "eventTime": Date().timeIntervalSince1970
        ])
    }
    
    // Handle notification tap
    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse, withCompletionHandler completionHandler: @escaping () -> Void) {
        // Track notification tap
        NewRelic.recordCustomEvent("PushNotificationTapped", attributes: [
            "actionIdentifier": response.actionIdentifier,
            "title": response.notification.request.content.title,
            "eventTime": Date().timeIntervalSince1970
        ])
        
        completionHandler()
    }
}
