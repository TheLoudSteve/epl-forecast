import Foundation
import SwiftUI
import NewRelic

class EPLService: ObservableObject {
    @Published var teams: [Team] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var lastUpdated: String?
    
    private let baseURL = "https://aiighxj72l.execute-api.us-west-2.amazonaws.com/prod"
    private var refreshTimer: Timer?
    private var isAppActive = true
    
    init() {
        fetchTeams()
        setupNotificationObservers()
        startPeriodicRefresh()
    }
    
    deinit {
        refreshTimer?.invalidate()
        NotificationCenter.default.removeObserver(self)
    }
    
    func fetchTeams() {
        isLoading = true
        errorMessage = nil
        
        // Track EPL data fetch start
        NewRelic.recordCustomEvent("EPLDataFetchStart", attributes: [
            "baseURL": baseURL,
            "timestamp": Date().timeIntervalSince1970
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
                        "url": self?.baseURL ?? "unknown"
                    ])
                    return
                }
                
                guard let httpResponse = response as? HTTPURLResponse else {
                    self?.errorMessage = "Unable to connect to server. Please try again."
                    
                    // Record response parsing error
                    NewRelic.recordCustomEvent("EPLDataFetchError", attributes: [
                        "error": "response_parsing_error",
                        "responseTime": responseTime
                    ])
                    return
                }
                
                guard 200...299 ~= httpResponse.statusCode else {
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
                    return
                }
                
                guard let data = data else {
                    self?.errorMessage = "No data available. Please try again."
                    
                    // Record no data error
                    NewRelic.recordCustomEvent("EPLDataFetchError", attributes: [
                        "error": "no_data",
                        "responseTime": responseTime,
                        "statusCode": httpResponse.statusCode
                    ])
                    return
                }
                
                do {
                    let apiResponse = try JSONDecoder().decode(APIResponse.self, from: data)
                    self?.teams = apiResponse.forecastTable
                    self?.lastUpdated = self?.formatDate(apiResponse.metadata.lastUpdated)
                    
                    // Record successful data fetch
                    NewRelic.recordCustomEvent("EPLDataFetchSuccess", attributes: [
                        "responseTime": responseTime,
                        "statusCode": httpResponse.statusCode,
                        "teamsCount": apiResponse.forecastTable.count,
                        "totalTeams": apiResponse.metadata.totalTeams,
                        "apiVersion": apiResponse.metadata.apiVersion,
                        "lastUpdated": apiResponse.metadata.lastUpdated
                    ])
                    
                } catch {
                    print("JSON decode error: \(error)")
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
        }.resume()
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
        fetchTeams() // Refresh when app becomes active
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
            self.fetchTeams()
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
}