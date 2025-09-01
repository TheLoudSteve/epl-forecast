import WidgetKit
import SwiftUI

struct Provider: TimelineProvider {
    func placeholder(in context: Context) -> TeamEntry {
        TeamEntry(date: Date(), team: sampleTeam())
    }

    func getSnapshot(in context: Context, completion: @escaping (TeamEntry) -> ()) {
        let entry = TeamEntry(date: Date(), team: sampleTeam())
        completion(entry)
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<Entry>) -> ()) {
        var entries: [TeamEntry] = []
        
        // Check if favorite team is set
        let favoriteTeam = SharedDataManager.shared.favoriteTeam
        
        guard favoriteTeam != nil else {
            // No favorite team set - show "set favorite team" state
            let entry = TeamEntry(date: Date(), team: noFavoriteTeamWidget())
            entries.append(entry)
            
            // Check again in 5 minutes in case user sets a favorite
            let nextUpdate = Calendar.current.date(byAdding: .minute, value: 5, to: Date())!
            let timeline = Timeline(entries: entries, policy: .after(nextUpdate))
            completion(timeline)
            return
        }
        
        // Try to get cached data first for faster widget loading
        if let favoriteTeam = SharedDataManager.shared.getFavoriteTeamData() {
            let widgetTeam = WidgetTeam(
                name: favoriteTeam.name,
                position: Int(favoriteTeam.forecastedPosition),
                points: favoriteTeam.forecastedPoints,
                primaryColor: teamPrimaryColor(for: favoriteTeam.name),
                backgroundColor: teamPrimaryColor(for: favoriteTeam.name).opacity(0.15),
                state: .loaded
            )
            let entry = TeamEntry(date: Date(), team: widgetTeam)
            entries.append(entry)
            
            // Update every 30 minutes
            let nextUpdate = Calendar.current.date(byAdding: .minute, value: 30, to: Date())!
            let timeline = Timeline(entries: entries, policy: .after(nextUpdate))
            completion(timeline)
            return
        }
        
        // Show "collecting data" state and fetch from API
        let collectingEntry = TeamEntry(date: Date(), team: collectingDataWidget())
        entries.append(collectingEntry)
        
        Task {
            do {
                _ = try await fetchFavoriteTeamData()
                // Don't add to entries here - the next timeline refresh will show loaded data
            } catch {
                print("Failed to fetch team data: \(error)")
                // Continue showing "collecting data" state
            }
        }
        
        // Retry in 2 minutes to check for data
        let nextUpdate = Calendar.current.date(byAdding: .minute, value: 2, to: Date())!
        let timeline = Timeline(entries: entries, policy: .after(nextUpdate))
        completion(timeline)
    }
}

struct TeamEntry: TimelineEntry {
    let date: Date
    let team: WidgetTeam
}

struct WidgetTeam {
    let name: String
    let position: Int?
    let points: Double?
    let primaryColor: Color
    let backgroundColor: Color
    let state: WidgetState
}

enum WidgetState {
    case loaded
    case noFavoriteTeam
    case collectingData
    case error
}

struct EPLForecastWidgetEntryView: View {
    var entry: Provider.Entry
    @Environment(\.widgetFamily) var widgetFamily

    var body: some View {
        switch widgetFamily {
        case .systemSmall:
            smallWidgetView
        case .systemMedium:
            mediumWidgetView
        default:
            smallWidgetView
        }
    }
    
    private var smallWidgetView: some View {
        VStack(spacing: 8) {
            // Header
            HStack {
                Text("EPL")
                    .font(.caption2)
                    .foregroundColor(.secondary)
                Spacer()
                Image(systemName: "soccerball")
                    .foregroundColor(.secondary)
                    .font(.caption2)
            }
            
            Spacer()
            
            // Main content based on state
            switch entry.team.state {
            case .loaded:
                loadedSmallContent
            case .noFavoriteTeam:
                noFavoriteTeamSmallContent
            case .collectingData:
                collectingDataSmallContent
            case .error:
                collectingDataSmallContent // Same as collecting for user experience
            }
            
            Spacer()
        }
        .padding()
        .containerBackground(entry.team.backgroundColor, for: .widget)
    }
    
    private var loadedSmallContent: some View {
        VStack(spacing: 4) {
            Text("#\(entry.team.position ?? 0)")
                .font(.system(size: 32, weight: .bold, design: .rounded))
                .foregroundColor(entry.team.primaryColor)
            
            Text(entry.team.name)
                .font(.headline)
                .fontWeight(.semibold)
                .foregroundColor(entry.team.primaryColor)
                .lineLimit(1)
                .minimumScaleFactor(0.8)
            
            Text("\(String(format: "%.0f", entry.team.points ?? 0)) pts")
                .font(.caption)
                .foregroundColor(.secondary)
            
            // Position indicator
            HStack {
                Circle()
                    .fill(positionColor(entry.team.position ?? 20))
                    .frame(width: 6, height: 6)
                
                Text(positionDescription(entry.team.position ?? 20))
                    .font(.caption2)
                    .foregroundColor(.secondary)
                    .lineLimit(1)
                
                Spacer()
            }
        }
    }
    
    private var noFavoriteTeamSmallContent: some View {
        VStack(spacing: 4) {
            Image(systemName: "star")
                .font(.system(size: 24))
                .foregroundColor(.secondary)
            
            Text("Open app to set your favorite team")
                .font(.caption)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .lineLimit(3)
        }
    }
    
    private var collectingDataSmallContent: some View {
        VStack(spacing: 4) {
            Image(systemName: "arrow.triangle.2.circlepath")
                .font(.system(size: 24))
                .foregroundColor(.secondary)
            
            Text("Collecting Data...")
                .font(.caption)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
    }
    
    private var mediumWidgetView: some View {
        VStack(spacing: 8) {
            // Header
            HStack {
                Text("EPL Forecast")
                    .font(.caption2)
                    .foregroundColor(.secondary)
                Spacer()
                Image(systemName: "soccerball")
                    .foregroundColor(.secondary)
                    .font(.caption2)
            }
            
            Spacer()
            
            // Main content based on state
            switch entry.team.state {
            case .loaded:
                loadedMediumContent
            case .noFavoriteTeam:
                noFavoriteTeamMediumContent
            case .collectingData:
                collectingDataMediumContent
            case .error:
                collectingDataMediumContent // Same as collecting for user experience
            }
            
            Spacer()
        }
        .padding()
        .containerBackground(entry.team.backgroundColor, for: .widget)
    }
    
    private var loadedMediumContent: some View {
        HStack(spacing: 16) {
            // Left side - Team info
            VStack(alignment: .leading, spacing: 4) {
                Text(entry.team.name)
                    .font(.title2)
                    .fontWeight(.bold)
                    .foregroundColor(entry.team.primaryColor)
                    .lineLimit(1)
                
                Text("\(String(format: "%.0f", entry.team.points ?? 0)) points")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                
                HStack {
                    Circle()
                        .fill(positionColor(entry.team.position ?? 20))
                        .frame(width: 8, height: 8)
                    
                    Text(positionDescription(entry.team.position ?? 20))
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            
            Spacer()
            
            // Right side - Large position number
            VStack {
                Text("#\(entry.team.position ?? 0)")
                    .font(.system(size: 48, weight: .bold, design: .rounded))
                    .foregroundColor(entry.team.primaryColor)
                
                Text("Position")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
    }
    
    private var noFavoriteTeamMediumContent: some View {
        VStack(spacing: 12) {
            Image(systemName: "star.circle")
                .font(.system(size: 36))
                .foregroundColor(.secondary)
            
            VStack(spacing: 4) {
                Text("No Favorite Team Set")
                    .font(.headline)
                    .foregroundColor(.primary)
                
                Text("Open the EPL Forecast app to select your favorite team and see live standings")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .lineLimit(3)
            }
        }
    }
    
    private var collectingDataMediumContent: some View {
        VStack(spacing: 12) {
            Image(systemName: "arrow.triangle.2.circlepath.circle")
                .font(.system(size: 36))
                .foregroundColor(.secondary)
            
            VStack(spacing: 4) {
                Text("Collecting Data")
                    .font(.headline)
                    .foregroundColor(.primary)
                
                Text("Loading the latest Premier League standings...")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }
        }
    }
    
    private func positionColor(_ position: Int) -> Color {
        switch position {
        case 1...4: return .blue
        case 18...20: return .red
        default: return .gray
        }
    }
    
    private func positionDescription(_ position: Int) -> String {
        switch position {
        case 1...4: return "Champions League"
        case 5: return "Europa League"
        case 18...20: return "Relegation Zone"
        default: return "Mid Table"
        }
    }
}

struct EPLForecastWidget: Widget {
    let kind: String = "EPLForecastWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: Provider()) { entry in
            EPLForecastWidgetEntryView(entry: entry)
        }
        .configurationDisplayName("EPL Team Forecast")
        .description("Track your favorite team's forecasted Premier League position.")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}

#Preview(as: .systemSmall) {
    EPLForecastWidget()
} timeline: {
    TeamEntry(date: .now, team: sampleTeam())
}

// MARK: - Helper Functions

func sampleTeam() -> WidgetTeam {
    return WidgetTeam(
        name: "Arsenal",
        position: 3,
        points: 68.5,
        primaryColor: Color(red: 0.8, green: 0, blue: 0),
        backgroundColor: Color(red: 0.8, green: 0, blue: 0).opacity(0.1),
        state: .loaded
    )
}

func noFavoriteTeamWidget() -> WidgetTeam {
    return WidgetTeam(
        name: "",
        position: nil,
        points: nil,
        primaryColor: .primary,
        backgroundColor: Color.gray.opacity(0.1),
        state: .noFavoriteTeam
    )
}

func collectingDataWidget() -> WidgetTeam {
    return WidgetTeam(
        name: "",
        position: nil,
        points: nil,
        primaryColor: .primary,
        backgroundColor: Color.blue.opacity(0.1),
        state: .collectingData
    )
}


func fetchFavoriteTeamData() async throws -> WidgetTeam {
    // Use the same API endpoint as the main app
    guard let url = URL(string: "https://1e4u1ghr3i.execute-api.us-east-1.amazonaws.com/dev/table") else {
        throw URLError(.badURL)
    }
    
    let (data, _) = try await URLSession.shared.data(from: url)
    let apiResponse = try JSONDecoder().decode(APIResponse.self, from: data)
    
    // Get favorite team from shared data
    let favoriteTeam = SharedDataManager.shared.favoriteTeam
    
    // Find the favorite team or default to first team
    let selectedTeam = apiResponse.forecastTable.first { team in
        favoriteTeam != nil && team.name.lowercased().contains(favoriteTeam!.lowercased())
    } ?? apiResponse.forecastTable.first!
    
    return WidgetTeam(
        name: selectedTeam.name,
        position: Int(selectedTeam.forecastedPosition),
        points: selectedTeam.forecastedPoints,
        primaryColor: teamPrimaryColor(for: selectedTeam.name),
        backgroundColor: teamPrimaryColor(for: selectedTeam.name).opacity(0.15),
        state: .loaded
    )
}

struct APIResponse: Codable {
    let forecastTable: [APITeam]
    let metadata: APIMetadata
    
    enum CodingKeys: String, CodingKey {
        case forecastTable = "forecast_table"
        case metadata
    }
}

struct APITeam: Codable {
    let name: String
    let forecastedPosition: Double
    let forecastedPoints: Double
    let played: Double
    let points: Double
    let pointsPerGame: Double
    
    enum CodingKeys: String, CodingKey {
        case name
        case forecastedPosition = "forecasted_position"
        case forecastedPoints = "forecasted_points"
        case played
        case points
        case pointsPerGame = "points_per_game"
    }
}

struct APIMetadata: Codable {
    let lastUpdated: String
    let totalTeams: Double
    let apiVersion: String
    let description: String
    
    enum CodingKeys: String, CodingKey {
        case lastUpdated = "last_updated"
        case totalTeams = "total_teams"
        case apiVersion = "api_version"
        case description
    }
}

func teamPrimaryColor(for teamName: String) -> Color {
    switch teamName.lowercased() {
    case let name where name.contains("arsenal"):
        return Color(red: 0.8, green: 0, blue: 0)
    case let name where name.contains("chelsea"):
        return Color(red: 0, green: 0.2, blue: 0.8)
    case let name where name.contains("liverpool"):
        return Color(red: 0.8, green: 0, blue: 0.2)
    case let name where name.contains("manchester city"):
        return Color(red: 0.4, green: 0.8, blue: 1)
    case let name where name.contains("manchester united"):
        return Color(red: 1, green: 0, blue: 0)
    case let name where name.contains("tottenham"):
        return Color(red: 0, green: 0.1, blue: 0.4)
    case let name where name.contains("newcastle"):
        return Color(red: 0, green: 0, blue: 0)
    case let name where name.contains("brighton"):
        return Color(red: 0, green: 0.4, blue: 1)
    case let name where name.contains("aston villa"):
        return Color(red: 0.5, green: 0, blue: 0.5)
    case let name where name.contains("west ham"):
        return Color(red: 0.5, green: 0, blue: 0.5)
    case let name where name.contains("crystal palace"):
        return Color(red: 0, green: 0.2, blue: 0.8)
    case let name where name.contains("wolves"):
        return Color(red: 1, green: 0.6, blue: 0)
    case let name where name.contains("fulham"):
        return Color(red: 0, green: 0, blue: 0)
    case let name where name.contains("brentford"):
        return Color(red: 1, green: 0, blue: 0)
    case let name where name.contains("nottingham"):
        return Color(red: 1, green: 0, blue: 0)
    case let name where name.contains("everton"):
        return Color(red: 0, green: 0.2, blue: 0.8)
    case let name where name.contains("bournemouth"):
        return Color(red: 1, green: 0, blue: 0)
    case let name where name.contains("luton"):
        return Color(red: 1, green: 0.6, blue: 0)
    case let name where name.contains("burnley"):
        return Color(red: 0.5, green: 0, blue: 0.5)
    case let name where name.contains("sheffield"):
        return Color(red: 1, green: 0, blue: 0)
    case let name where name.contains("leicester"):
        return Color(red: 0, green: 0.2, blue: 0.8)
    case let name where name.contains("leeds"):
        return Color.white
    case let name where name.contains("southampton"):
        return Color(red: 1, green: 0, blue: 0)
    default:
        return Color.primary
    }
}