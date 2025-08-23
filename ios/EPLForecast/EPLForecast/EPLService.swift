import Foundation
import SwiftUI

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
        
        guard let url = URL(string: "\(baseURL)/table") else {
            errorMessage = "Invalid URL"
            isLoading = false
            return
        }
        
        URLSession.shared.dataTask(with: url) { [weak self] data, response, error in
            DispatchQueue.main.async {
                self?.isLoading = false
                
                if let error = error {
                    if error.localizedDescription.contains("offline") || error.localizedDescription.contains("network") {
                        self?.errorMessage = "No internet connection. Please check your network and try again."
                    } else {
                        self?.errorMessage = "Connection failed. Please try again later."
                    }
                    return
                }
                
                guard let httpResponse = response as? HTTPURLResponse else {
                    self?.errorMessage = "Unable to connect to server. Please try again."
                    return
                }
                
                guard 200...299 ~= httpResponse.statusCode else {
                    switch httpResponse.statusCode {
                    case 500...599:
                        self?.errorMessage = "Server is temporarily unavailable. Please try again in a few minutes."
                    case 400...499:
                        self?.errorMessage = "Unable to load data. Please try again."
                    default:
                        self?.errorMessage = "Something went wrong. Please try again later."
                    }
                    return
                }
                
                guard let data = data else {
                    self?.errorMessage = "No data available. Please try again."
                    return
                }
                
                do {
                    let apiResponse = try JSONDecoder().decode(APIResponse.self, from: data)
                    self?.teams = apiResponse.forecastTable
                    self?.lastUpdated = self?.formatDate(apiResponse.metadata.lastUpdated)
                } catch {
                    print("JSON decode error: \(error)")
                    self?.errorMessage = "Unable to process data. The server may be updating. Please try again in a moment."
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