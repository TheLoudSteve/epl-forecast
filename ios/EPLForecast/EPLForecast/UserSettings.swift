import SwiftUI
import Combine
import WidgetKit

enum NotificationTiming: String, CaseIterable {
    case immediate = "immediate"
    case endOfDay = "end_of_day"
    
    var displayName: String {
        switch self {
        case .immediate:
            return "Immediate"
        case .endOfDay:
            return "End of Day"
        }
    }
    
    var description: String {
        switch self {
        case .immediate:
            return "Get notified as soon as forecast changes occur"
        case .endOfDay:
            return "Get a summary after all games are finished for the day"
        }
    }
}

enum NotificationSensitivity: String, CaseIterable {
    case anyChange = "any_change"
    case significantOnly = "significant_only"
    
    var displayName: String {
        switch self {
        case .anyChange:
            return "Any Position Change"
        case .significantOnly:
            return "Significant Changes Only"
        }
    }
    
    var description: String {
        switch self {
        case .anyChange:
            return "Notify for any movement up or down in forecast"
        case .significantOnly:
            return "Notify for title, Champions League, or relegation changes"
        }
    }
}

class UserSettings: ObservableObject {
    static let shared = UserSettings()
    
    private let iCloudStore = NSUbiquitousKeyValueStore.default
    private var cancellables = Set<AnyCancellable>()
    
    @Published var favoriteTeam: String? {
        didSet {
            // Save to both local UserDefaults and iCloud
            UserDefaults.standard.set(favoriteTeam, forKey: "favoriteTeam")
            
            iCloudStore.set(favoriteTeam ?? "", forKey: "favoriteTeam")
            iCloudStore.synchronize()
            
            // Also save to shared container for widget
            SharedDataManager.shared.favoriteTeam = favoriteTeam
            
            // Force widget refresh when favorite team changes
            WidgetCenter.shared.reloadAllTimelines()
            
            // Force synchronization
            UserDefaults.standard.synchronize()
        }
    }
    
    @Published var hasLaunchedBefore: Bool = false {
        didSet {
            UserDefaults.standard.set(hasLaunchedBefore, forKey: "hasLaunchedBefore")
            iCloudStore.set(hasLaunchedBefore, forKey: "hasLaunchedBefore")
            iCloudStore.synchronize()
        }
    }
    
    // MARK: - Notification Preferences
    
    @Published var notificationsEnabled: Bool = true {
        didSet {
            UserDefaults.standard.set(notificationsEnabled, forKey: "notificationsEnabled")
            iCloudStore.set(notificationsEnabled, forKey: "notificationsEnabled")
            iCloudStore.synchronize()
        }
    }
    
    @Published var notificationTiming: NotificationTiming = .immediate {
        didSet {
            UserDefaults.standard.set(notificationTiming.rawValue, forKey: "notificationTiming")
            iCloudStore.set(notificationTiming.rawValue, forKey: "notificationTiming")
            iCloudStore.synchronize()
        }
    }
    
    @Published var notificationSensitivity: NotificationSensitivity = .anyChange {
        didSet {
            UserDefaults.standard.set(notificationSensitivity.rawValue, forKey: "notificationSensitivity")
            iCloudStore.set(notificationSensitivity.rawValue, forKey: "notificationSensitivity")
            iCloudStore.synchronize()
        }
    }

    private init() {
        // Load from iCloud if available, otherwise from UserDefaults
        let iCloudFavoriteTeam = iCloudStore.string(forKey: "favoriteTeam")
        let localFavoriteTeam = UserDefaults.standard.string(forKey: "favoriteTeam")
        
        let iCloudHasLaunched = iCloudStore.bool(forKey: "hasLaunchedBefore")
        let localHasLaunched = UserDefaults.standard.bool(forKey: "hasLaunchedBefore")
        
        // Load notification preferences
        let iCloudNotificationsEnabled = iCloudStore.object(forKey: "notificationsEnabled") as? Bool
        let localNotificationsEnabled = UserDefaults.standard.object(forKey: "notificationsEnabled") as? Bool
        
        let iCloudTimingRaw = iCloudStore.string(forKey: "notificationTiming")
        let localTimingRaw = UserDefaults.standard.string(forKey: "notificationTiming")
        
        let iCloudSensitivityRaw = iCloudStore.string(forKey: "notificationSensitivity") 
        let localSensitivityRaw = UserDefaults.standard.string(forKey: "notificationSensitivity")
        
        // Use iCloud data if it exists and is not empty, otherwise use local
        if let iCloudTeam = iCloudFavoriteTeam, !iCloudTeam.isEmpty {
            self.favoriteTeam = iCloudTeam
        } else {
            self.favoriteTeam = localFavoriteTeam
        }
        
        // For boolean, use iCloud if it's been launched before there
        self.hasLaunchedBefore = iCloudHasLaunched || localHasLaunched
        
        // Load notification preferences with defaults
        self.notificationsEnabled = iCloudNotificationsEnabled ?? localNotificationsEnabled ?? true
        
        if let timingRaw = iCloudTimingRaw ?? localTimingRaw,
           let timing = NotificationTiming(rawValue: timingRaw) {
            self.notificationTiming = timing
        } else {
            self.notificationTiming = .immediate
        }
        
        if let sensitivityRaw = iCloudSensitivityRaw ?? localSensitivityRaw,
           let sensitivity = NotificationSensitivity(rawValue: sensitivityRaw) {
            self.notificationSensitivity = sensitivity
        } else {
            self.notificationSensitivity = .anyChange
        }
        
        // Sync with SharedDataManager for widget
        SharedDataManager.shared.favoriteTeam = self.favoriteTeam
        
        // Set up iCloud sync after initialization
        setupiCloudSync()
    }
    
    
    private func setupiCloudSync() {
        // Listen for iCloud changes
        NotificationCenter.default.publisher(for: NSUbiquitousKeyValueStore.didChangeExternallyNotification)
            .sink { [weak self] notification in
                DispatchQueue.main.async {
                    self?.handleiCloudChange(notification)
                }
            }
            .store(in: &cancellables)
    }
    
    private func handleiCloudChange(_ notification: Notification) {
        guard let userInfo = notification.userInfo,
              let changedKeys = userInfo[NSUbiquitousKeyValueStoreChangedKeysKey] as? [String] else {
            return
        }
        
        for key in changedKeys {
            switch key {
            case "favoriteTeam":
                let newValue = iCloudStore.string(forKey: "favoriteTeam")
                if newValue != self.favoriteTeam {
                    self.favoriteTeam = newValue?.isEmpty == false ? newValue : nil
                }
            case "hasLaunchedBefore":
                let newValue = iCloudStore.bool(forKey: "hasLaunchedBefore")
                if newValue != self.hasLaunchedBefore {
                    self.hasLaunchedBefore = newValue
                }
            case "notificationsEnabled":
                let newValue = iCloudStore.bool(forKey: "notificationsEnabled")
                if newValue != self.notificationsEnabled {
                    self.notificationsEnabled = newValue
                }
            case "notificationTiming":
                if let newValueRaw = iCloudStore.string(forKey: "notificationTiming"),
                   let newValue = NotificationTiming(rawValue: newValueRaw),
                   newValue != self.notificationTiming {
                    self.notificationTiming = newValue
                }
            case "notificationSensitivity":
                if let newValueRaw = iCloudStore.string(forKey: "notificationSensitivity"),
                   let newValue = NotificationSensitivity(rawValue: newValueRaw),
                   newValue != self.notificationSensitivity {
                    self.notificationSensitivity = newValue
                }
            default:
                break
            }
        }
    }
    
    var showOnboarding: Bool {
        return !hasLaunchedBefore
    }
    
    func setFavoriteTeam(_ teamName: String) {
        favoriteTeam = teamName
        hasLaunchedBefore = true
    }
}

// Team colors mapping
extension Team {
    var primaryColor: Color {
        switch name.lowercased() {
        case let name where name.contains("arsenal"):
            return Color(red: 0.8, green: 0, blue: 0) // Arsenal red
        case let name where name.contains("chelsea"):
            return Color(red: 0, green: 0.2, blue: 0.8) // Chelsea blue
        case let name where name.contains("liverpool"):
            return Color(red: 0.8, green: 0, blue: 0.2) // Liverpool red
        case let name where name.contains("manchester city"):
            return Color(red: 0.4, green: 0.8, blue: 1) // Man City sky blue
        case let name where name.contains("manchester united"):
            return Color(red: 1, green: 0, blue: 0) // Man United red
        case let name where name.contains("tottenham"):
            return Color(red: 0, green: 0.1, blue: 0.4) // Tottenham navy
        case let name where name.contains("newcastle"):
            return Color(red: 0, green: 0, blue: 0) // Newcastle black
        case let name where name.contains("brighton"):
            return Color(red: 0, green: 0.4, blue: 1) // Brighton blue
        case let name where name.contains("aston villa"):
            return Color(red: 0.5, green: 0, blue: 0.5) // Aston Villa claret
        case let name where name.contains("west ham"):
            return Color(red: 0.5, green: 0, blue: 0.5) // West Ham claret
        case let name where name.contains("crystal palace"):
            return Color(red: 0, green: 0.2, blue: 0.8) // Palace blue
        case let name where name.contains("wolves"):
            return Color(red: 1, green: 0.6, blue: 0) // Wolves gold
        case let name where name.contains("fulham"):
            return Color(red: 0, green: 0, blue: 0) // Fulham black
        case let name where name.contains("brentford"):
            return Color(red: 1, green: 0, blue: 0) // Brentford red
        case let name where name.contains("nottingham"):
            return Color(red: 1, green: 0, blue: 0) // Forest red
        case let name where name.contains("everton"):
            return Color(red: 0, green: 0.2, blue: 0.8) // Everton blue
        case let name where name.contains("bournemouth"):
            return Color(red: 1, green: 0, blue: 0) // Bournemouth red
        case let name where name.contains("luton"):
            return Color(red: 1, green: 0.6, blue: 0) // Luton orange
        case let name where name.contains("burnley"):
            return Color(red: 0.5, green: 0, blue: 0.5) // Burnley claret
        case let name where name.contains("sheffield"):
            return Color(red: 1, green: 0, blue: 0) // Sheffield red
        case let name where name.contains("leicester"):
            return Color(red: 0, green: 0.2, blue: 0.8) // Leicester blue
        case let name where name.contains("leeds"):
            return Color(red: 0, green: 0.2, blue: 0.8) // Leeds blue (readable alternative)
        case let name where name.contains("southampton"):
            return Color(red: 1, green: 0, blue: 0) // Southampton red
        default:
            return Color.primary
        }
    }
    
    var backgroundColor: Color {
        primaryColor.opacity(0.15)
    }
}