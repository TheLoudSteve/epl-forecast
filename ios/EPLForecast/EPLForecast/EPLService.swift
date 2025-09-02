import Foundation
import SwiftUI
import NewRelic
import WidgetKit

class EPLService: ObservableObject {
    @Published var teams: [Team] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var lastUpdated: String?
    
    private let baseURL = "https://1e4u1ghr3i.execute-api.us-east-1.amazonaws.com/dev"  // Temporarily pointing to dev for notification testing
    private var refreshTimer: Timer?
    private var isAppActive = true
    
    init() {
        loadCachedDataFirst()
        fetchTeamsInBackground()
        setupNotificationObservers()
        startPeriodicRefresh()
    }
    
    deinit {
        refreshTimer?.invalidate()
        NotificationCenter.default.removeObserver(self)
    }
    
    // MARK: - Cache-First Loading Strategy
    
    private func loadCachedDataFirst() {
        // Load any cached data immediately (even if older than 30 min) to show something
        if let cachedTeams = SharedDataManager.shared.getAnyCachedTeamData() {
            self.teams = cachedTeams
            // Don't set isLoading = false here - we want to fetch fresh data
            
            // Set a cached timestamp if available
            if let cacheTimestamp = UserDefaults(suiteName: "group.com.LoudSteve.EplForecast.EPLForecast")?.object(forKey: "cacheTimestamp") as? Date {
                self.lastUpdated = formatDate(cacheTimestamp.ISO8601Format())
            }
        }
    }
    
    private func fetchTeamsInBackground() {
        // Only show loading state if we have no cached data at all
        if teams.isEmpty {
            isLoading = true
        }
        errorMessage = nil
        
        // Track EPL data fetch start
        NewRelic.recordCustomEvent("EPLDataFetchStart", attributes: [
            "baseURL": baseURL,
            "startTime": Date().timeIntervalSince1970,
            "hasCachedData": !teams.isEmpty
        ])
        
        guard let url = URL(string: "\(baseURL)/table") else {
            let error = "Invalid URL"
            errorMessage = error
            isLoading = false
            
            // Record URL validation error
            NewRelic.recordCustomEvent("EPLDataFetchError", attributes: [
                "error": "invalid_url",
                "url": "\(baseURL)/table"
            ])
            return
        }
        
        let startTime = Date()
        URLSession.shared.dataTask(with: url) { [weak self] data, response, error in
            let responseTime = Date().timeIntervalSince(startTime) * 1000 // Convert to milliseconds
            
            DispatchQueue.main.async {
                self?.isLoading = false
                
                if let error = error {
                    // Only show error if we have no cached data to display
                    if self?.teams.isEmpty == true {
                        let errorType: String
                        if error.localizedDescription.contains("offline") || error.localizedDescription.contains("network") {
                            errorType = "network_error"
                            self?.errorMessage = "No internet connection. Please check your network and try again."
                        } else {
                            errorType = "connection_error"
                            self?.errorMessage = "Connection failed. Please try again later."
                        }
                        
                        // Record network error with details
                        NewRelic.recordCustomEvent("EPLDataFetchError", attributes: [
                            "error": errorType,
                            "errorDescription": error.localizedDescription,
                            "responseTime": responseTime,
                            "url": self?.baseURL ?? "unknown",
                            "hasCachedData": self?.teams.isEmpty == false
                        ])
                    }
                    return
                }
                
                guard let httpResponse = response as? HTTPURLResponse else {
                    if self?.teams.isEmpty == true {
                        self?.errorMessage = "Unable to connect to server. Please try again."
                        
                        // Record response parsing error
                        NewRelic.recordCustomEvent("EPLDataFetchError", attributes: [
                            "error": "response_parsing_error",
                            "responseTime": responseTime
                        ])
                    }
                    return
                }
                
                guard 200...299 ~= httpResponse.statusCode else {
                    if self?.teams.isEmpty == true {
                        let statusCode = httpResponse.statusCode
                        let errorMessage: String
                        
                        switch statusCode {
                        case 500...599:
                            errorMessage = "Server is temporarily unavailable. Please try again in a few minutes."
                        case 400...499:
                            errorMessage = "Unable to load data. Please try again."
                        default:
                            errorMessage = "Something went wrong. Please try again later."
                        }
                        
                        self?.errorMessage = errorMessage
                        
                        // Record HTTP error with status code
                        NewRelic.recordCustomEvent("EPLDataFetchError", attributes: [
                            "error": "http_error",
                            "statusCode": statusCode,
                            "errorMessage": errorMessage,
                            "responseTime": responseTime
                        ])
                    }
                    return
                }
                
                guard let data = data else {
                    if self?.teams.isEmpty == true {
                        self?.errorMessage = "No data available. Please try again."
                        
                        // Record no data error
                        NewRelic.recordCustomEvent("EPLDataFetchError", attributes: [
                            "error": "no_data",
                            "responseTime": responseTime,
                            "statusCode": httpResponse.statusCode
                        ])
                    }
                    return
                }
                
                do {
                    let apiResponse = try JSONDecoder().decode(APIResponse.self, from: data)
                    
                    // Always update with fresh data
                    self?.teams = apiResponse.forecastTable
                    self?.lastUpdated = self?.formatDate(apiResponse.metadata.lastUpdated)
                    self?.errorMessage = nil // Clear any previous errors
                    
                    // Cache data for widget
                    SharedDataManager.shared.cacheTeamData(apiResponse.forecastTable)
                    
                    // Trigger widget refresh
                    WidgetCenter.shared.reloadAllTimelines()
                    
                    // Record successful data fetch
                    NewRelic.recordCustomEvent("EPLDataFetchSuccess", attributes: [
                        "responseTime": responseTime,
                        "statusCode": httpResponse.statusCode,
                        "teamsCount": apiResponse.forecastTable.count,
                        "totalTeams": apiResponse.metadata.totalTeams,
                        "apiVersion": apiResponse.metadata.apiVersion,
                        "lastUpdated": apiResponse.metadata.lastUpdated,
                        "hadCachedData": self?.teams.isEmpty == false
                    ])
                    
                } catch {
                    print("JSON decode error: \(error)")
                    if self?.teams.isEmpty == true {
                        self?.errorMessage = "Unable to process data. The server may be updating. Please try again in a moment."
                        
                        // Record JSON parsing error
                        NewRelic.recordCustomEvent("EPLDataFetchError", attributes: [
                            "error": "json_parsing_error",
                            "errorDescription": error.localizedDescription,
                            "responseTime": responseTime,
                            "statusCode": httpResponse.statusCode,
                            "dataSize": data.count
                        ])
                    }
                }
            }
        }.resume()
    }
    
    func fetchTeams() {
        // Use the new background loading approach
        fetchTeamsInBackground()
    }
    
    func refreshData() {
        fetchTeams()
    }
    
    // MARK: - App Lifecycle and Periodic Refresh
    
    private func setupNotificationObservers() {
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(appDidBecomeActive),
            name: UIApplication.didBecomeActiveNotification,
            object: nil
        )
        
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(appWillResignActive),
            name: UIApplication.willResignActiveNotification,
            object: nil
        )
    }
    
    @objc private func appDidBecomeActive() {
        isAppActive = true
        
        // Only fetch fresh data if our cache is older than 5 minutes
        if let cacheTimestamp = UserDefaults(suiteName: "group.com.LoudSteve.EplForecast.EPLForecast")?.object(forKey: "cacheTimestamp") as? Date {
            if Date().timeIntervalSince(cacheTimestamp) > 5 * 60 {
                fetchTeams()
            }
        } else {
            fetchTeams() // No cache timestamp, fetch fresh data
        }
        
        startPeriodicRefresh() // Resume 60-second timer
    }
    
    @objc private func appWillResignActive() {
        isAppActive = false
        stopPeriodicRefresh() // Pause timer when app goes to background
    }
    
    private func startPeriodicRefresh() {
        stopPeriodicRefresh() // Clear any existing timer
        
        refreshTimer = Timer.scheduledTimer(withTimeInterval: 60.0, repeats: true) { [weak self] _ in
            guard let self = self, self.isAppActive else { return }
            
            // Only fetch if cache is older than 2 minutes during periodic refresh
            if let cacheTimestamp = UserDefaults(suiteName: "group.com.LoudSteve.EplForecast.EPLForecast")?.object(forKey: "cacheTimestamp") as? Date {
                if Date().timeIntervalSince(cacheTimestamp) > 2 * 60 {
                    self.fetchTeams()
                }
            } else {
                self.fetchTeams()
            }
        }
    }
    
    private func stopPeriodicRefresh() {
        refreshTimer?.invalidate()
        refreshTimer = nil
    }
    
    private func formatDate(_ isoString: String) -> String {
        let formatter = ISO8601DateFormatter()
        guard let date = formatter.date(from: isoString) else {
            return isoString
        }
        
        let displayFormatter = DateFormatter()
        displayFormatter.dateStyle = .medium
        displayFormatter.timeStyle = .short
        displayFormatter.timeZone = TimeZone.current
        
        return displayFormatter.string(from: date)
    }
    
    // MARK: - Notification Methods
    
    func sendTestNotification(completion: @escaping (Result<String, Error>) -> Void) {
        guard let url = URL(string: "\(baseURL)/preferences/test") else {
            completion(.failure(APIError.invalidURL))
            return
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        // Generate a simple user ID based on device
        let userID = UIDevice.current.identifierForVendor?.uuidString ?? "unknown_device"
        request.setValue(userID, forHTTPHeaderField: "X-User-ID")
        
        // Track test notification attempt
        NewRelic.recordCustomEvent("TestNotificationAttempted", attributes: [
            "userId": userID,
            "baseURL": baseURL
        ])
        
        URLSession.shared.dataTask(with: request) { data, response, error in
            DispatchQueue.main.async {
                if let error = error {
                    NewRelic.recordCustomEvent("TestNotificationFailed", attributes: [
                        "error": error.localizedDescription
                    ])
                    completion(.failure(error))
                    return
                }
                
                guard let httpResponse = response as? HTTPURLResponse else {
                    completion(.failure(APIError.invalidResponse))
                    return
                }
                
                if httpResponse.statusCode == 200 {
                    NewRelic.recordCustomEvent("TestNotificationSuccess", attributes: [
                        "statusCode": httpResponse.statusCode
                    ])
                    completion(.success("Test notification sent successfully!"))
                } else {
                    let errorMessage = "Failed to send test notification (Status: \(httpResponse.statusCode))"
                    NewRelic.recordCustomEvent("TestNotificationFailed", attributes: [
                        "statusCode": httpResponse.statusCode,
                        "error": errorMessage
                    ])
                    completion(.failure(APIError.custom(errorMessage)))
                }
            }
        }.resume()
    }
}

enum APIError: Error, LocalizedError {
    case invalidURL
    case invalidResponse
    case custom(String)
    
    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid URL"
        case .invalidResponse:
            return "Invalid response"
        case .custom(let message):
            return message
        }
    }
}