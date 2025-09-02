import Foundation

class SharedDataManager {
    static let shared = SharedDataManager()
    
    // App Group identifier for sharing data between main app and widget
    private let appGroupIdentifier = "group.com.LoudSteve.EplForecast.EPLForecast"
    
    private var sharedDefaults: UserDefaults? {
        return UserDefaults(suiteName: appGroupIdentifier)
    }
    
    private init() {}
    
    // MARK: - Favorite Team
    
    var favoriteTeam: String? {
        get {
            // Use file-based storage for reliable app group sharing
            guard let containerURL = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: appGroupIdentifier) else {
                return nil
            }
            
            let favoriteTeamFile = containerURL.appendingPathComponent("favoriteTeam.txt")
            
            do {
                let favoriteTeam = try String(contentsOf: favoriteTeamFile, encoding: .utf8).trimmingCharacters(in: .whitespacesAndNewlines)
                return favoriteTeam.isEmpty ? nil : favoriteTeam
            } catch {
                return nil
            }
        }
        set {
            // Write to app group file (preferred method)
            if let containerURL = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: appGroupIdentifier) {
                let favoriteTeamFile = containerURL.appendingPathComponent("favoriteTeam.txt")
                
                do {
                    if let newValue = newValue {
                        try newValue.write(to: favoriteTeamFile, atomically: true, encoding: .utf8)
                    }
                } catch {
                    // File write failed, UserDefaults will serve as fallback
                }
            }
            
            // Also write to UserDefaults (fallback for widget)
            sharedDefaults?.set(newValue, forKey: "favoriteTeam")
            sharedDefaults?.synchronize()
        }
    }
    
    // MARK: - Team Data Cache
    
    func cacheTeamData(_ teams: [Team]) {
        do {
            let encoder = JSONEncoder()
            let data = try encoder.encode(teams)
            sharedDefaults?.set(data, forKey: "cachedTeams")
            sharedDefaults?.set(Date(), forKey: "cacheTimestamp")
        } catch {
            print("Failed to cache team data: \(error)")
        }
    }
    
    func getCachedTeamData() -> [Team]? {
        guard let data = sharedDefaults?.data(forKey: "cachedTeams"),
              let cacheTimestamp = sharedDefaults?.object(forKey: "cacheTimestamp") as? Date else {
            return nil
        }
        
        // Check if cache is less than 30 minutes old
        if Date().timeIntervalSince(cacheTimestamp) > 30 * 60 {
            return nil
        }
        
        do {
            let decoder = JSONDecoder()
            return try decoder.decode([Team].self, from: data)
        } catch {
            return nil
        }
    }
    
    // Get any cached team data, regardless of age (for immediate display)
    func getAnyCachedTeamData() -> [Team]? {
        guard let data = sharedDefaults?.data(forKey: "cachedTeams") else {
            return nil
        }
        
        do {
            let decoder = JSONDecoder()
            return try decoder.decode([Team].self, from: data)
        } catch {
            return nil
        }
    }
    
    func getFavoriteTeamData() -> Team? {
        guard let favoriteTeam = favoriteTeam,
              let teams = getCachedTeamData() else {
            return nil
        }
        
        return teams.first { team in
            team.name.lowercased().contains(favoriteTeam.lowercased())
        }
    }
}

