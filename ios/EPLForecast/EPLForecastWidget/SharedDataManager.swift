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
            // Try App Group file first
            if let containerURL = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: appGroupIdentifier) {
                let favoriteTeamFile = containerURL.appendingPathComponent("favoriteTeam.txt")
                
                do {
                    let favoriteTeam = try String(contentsOf: favoriteTeamFile, encoding: .utf8).trimmingCharacters(in: .whitespacesAndNewlines)
                    return favoriteTeam.isEmpty ? nil : favoriteTeam
                } catch {
                    // File doesn't exist or couldn't be read, fall through to UserDefaults
                }
            }
            
            // Fallback to shared UserDefaults
            let sharedTeam = sharedDefaults?.string(forKey: "favoriteTeam")
            if let sharedTeam = sharedTeam, !sharedTeam.isEmpty {
                return sharedTeam
            }
            
            // Final fallback: try standard UserDefaults
            let standardTeam = UserDefaults.standard.string(forKey: "favoriteTeam")
            if let standardTeam = standardTeam, !standardTeam.isEmpty {
                return standardTeam
            }
            
            return nil
        }
        set {
            // Write to app group file
            if let containerURL = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: appGroupIdentifier) {
                let favoriteTeamFile = containerURL.appendingPathComponent("favoriteTeam.txt")
                do {
                    if let newValue = newValue {
                        try newValue.write(to: favoriteTeamFile, atomically: true, encoding: .utf8)
                    }
                } catch {
                    // File write failed, UserDefaults will serve as backup
                }
            }
            
            // Also write to UserDefaults as backup
            sharedDefaults?.set(newValue, forKey: "favoriteTeam")
            sharedDefaults?.synchronize()
        }
    }
    
    // MARK: - Team Data Cache
    
    func cacheTeamData(_ teamsData: Data) {
        sharedDefaults?.set(teamsData, forKey: "cachedTeams")
        sharedDefaults?.set(Date(), forKey: "cacheTimestamp")
    }
    
    func getCachedTeamData() -> Data? {
        guard let data = sharedDefaults?.data(forKey: "cachedTeams"),
              let cacheTimestamp = sharedDefaults?.object(forKey: "cacheTimestamp") as? Date else {
            return nil
        }
        
        // Check if cache is less than 4 hours old
        if Date().timeIntervalSince(cacheTimestamp) > 4 * 60 * 60 {
            return nil
        }
        
        return data
    }
    
    func getFavoriteTeamData() -> Team? {
        guard let favoriteTeam = favoriteTeam,
              let cachedData = getCachedTeamData() else {
            return nil
        }
        
        do {
            let decoder = JSONDecoder()
            let teams = try decoder.decode([Team].self, from: cachedData)
            
            return teams.first { team in
                team.name.lowercased().contains(favoriteTeam.lowercased())
            }
        } catch {
            print("Failed to decode cached team data: \(error)")
            return nil
        }
    }
}

