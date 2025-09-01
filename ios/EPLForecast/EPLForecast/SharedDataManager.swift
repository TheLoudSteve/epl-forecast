import Foundation

class SharedDataManager {
    static let shared = SharedDataManager()
    
    // App Group identifier for sharing data between main app and widget
    private let appGroupIdentifier = "group.com.LoudSteve.EplForecast.EPLForecast"
    
    private var sharedDefaults: UserDefaults? {
        let defaults = UserDefaults(suiteName: appGroupIdentifier)
        print("Main App SharedDataManager - App Group ID: \(appGroupIdentifier)")
        print("Main App SharedDataManager - SharedDefaults created: \(defaults != nil ? "success" : "failed")")
        return defaults
    }
    
    private init() {}
    
    // MARK: - Favorite Team
    
    var favoriteTeam: String? {
        get {
            // Use file-based storage for reliable app group sharing
            guard let containerURL = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: appGroupIdentifier) else {
                print("Main App SharedDataManager - Failed to get app group container URL")
                return nil
            }
            
            let favoriteTeamFile = containerURL.appendingPathComponent("favoriteTeam.txt")
            print("Main App SharedDataManager - Reading from file: \(favoriteTeamFile.path)")
            
            do {
                let favoriteTeam = try String(contentsOf: favoriteTeamFile, encoding: .utf8).trimmingCharacters(in: .whitespacesAndNewlines)
                print("Main App SharedDataManager - Read favorite team from file: \(favoriteTeam)")
                return favoriteTeam.isEmpty ? nil : favoriteTeam
            } catch {
                print("Main App SharedDataManager - Failed to read favorite team file: \(error)")
                return nil
            }
        }
        set {
            print("Main App SharedDataManager - Set favoriteTeam to: \(newValue ?? "nil")")
            
            // Write to app group file (preferred method)
            if let containerURL = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: appGroupIdentifier) {
                let favoriteTeamFile = containerURL.appendingPathComponent("favoriteTeam.txt")
                print("Main App SharedDataManager - Writing to app group file: \(favoriteTeamFile.path)")
                
                do {
                    if let newValue = newValue {
                        try newValue.write(to: favoriteTeamFile, atomically: true, encoding: .utf8)
                        print("Main App SharedDataManager - Successfully wrote to file: \(newValue)")
                        
                        // Verify immediately
                        let verification = try String(contentsOf: favoriteTeamFile, encoding: .utf8)
                        print("Main App SharedDataManager - File verification read: \(verification)")
                    }
                } catch {
                    print("Main App SharedDataManager - Failed to write to file: \(error)")
                }
            } else {
                print("Main App SharedDataManager - App group container not accessible")
            }
            
            // Also write to UserDefaults (fallback for widget)
            sharedDefaults?.set(newValue, forKey: "favoriteTeam")
            sharedDefaults?.synchronize()
            print("Main App SharedDataManager - Also wrote to UserDefaults: \(newValue ?? "nil")")
            
            // Verify UserDefaults write
            let userDefaultsVerify = sharedDefaults?.string(forKey: "favoriteTeam")
            print("Main App SharedDataManager - UserDefaults verification: \(userDefaultsVerify ?? "nil")")
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
            print("Failed to decode cached team data: \(error)")
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

