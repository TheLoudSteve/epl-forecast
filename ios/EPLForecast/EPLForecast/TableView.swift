import SwiftUI
import NewRelic

struct TableView: View {
    @StateObject private var eplService = EPLService()
    @ObservedObject private var userSettings = UserSettings.shared
    @State private var scrollPosition: String?
    @Binding var shouldResetScroll: Bool
    @State private var showForecast = true
    
    // Computed property for sorted teams based on current view mode
    var sortedTeams: [Team] {
        if showForecast {
            return eplService.teams.sorted { $0.forecastedPosition < $1.forecastedPosition }
        } else {
            return eplService.teams.sorted { $0.currentPosition < $1.currentPosition }
        }
    }

    // Get forecast-sorted teams
    var forecastSortedTeams: [Team] {
        eplService.teams.sorted { $0.forecastedPosition < $1.forecastedPosition }
    }

    // Calculate PPG needed in remaining games to reach a target
    func calculatePPGToTarget(for team: Team, targetPPG: Double, totalGames: Int = 38) -> String {
        // Calculate target's projected points
        let targetProjected = round(targetPPG * Double(totalGames))

        // Points needed to exceed target
        let pointsNeeded = (targetProjected + 1) - Double(team.points)

        // Games remaining for this team
        let gamesRemaining = totalGames - team.played

        // If no games remaining, can't improve
        if gamesRemaining <= 0 {
            return "Not Possible"
        }

        // Required PPG in remaining games
        let requiredPPG = pointsNeeded / Double(gamesRemaining)

        // If required PPG > 3.0, show >3.00 (needs leader to drop points)
        if requiredPPG > 3.0 {
            return ">3.00"
        }

        // If required PPG <= 0, they're already projected ahead
        if requiredPPG <= 0 {
            return "0.00"
        }

        return String(format: "%.2f", requiredPPG)
    }

    // Get contextual PPG target based on forecasted position
    func getContextualPPG(for team: Team) -> (value: String, label: String) {
        let position = team.forecastedPosition
        let sorted = forecastSortedTeams

        // 1st place - N/A
        if position == 1 {
            return ("N/A", "PPG for 1st")
        }

        // 2nd-4th - PPG for 1st (chasing title)
        if position >= 2 && position <= 4 {
            let leaderPPG = sorted.first?.pointsPerGame ?? 0
            return (calculatePPGToTarget(for: team, targetPPG: leaderPPG), "PPG for 1st")
        }

        // 5th-17th - PPG for Top 4 (chasing Champions League)
        if position >= 5 && position <= 17 {
            let fourthPlacePPG = sorted.count > 3 ? sorted[3].pointsPerGame : 0
            return (calculatePPGToTarget(for: team, targetPPG: fourthPlacePPG), "PPG for Top 4")
        }

        // 18th-20th - PPG for Safety (avoiding relegation)
        if position >= 18 {
            let seventeenthPlacePPG = sorted.count > 16 ? sorted[16].pointsPerGame : 0
            return (calculatePPGToTarget(for: team, targetPPG: seventeenthPlacePPG), "PPG for Safety")
        }

        return ("N/A", "")
    }
    
    var body: some View {
        VStack {
            if eplService.isLoading {
                VStack(spacing: 20) {
                    ProgressView()
                        .scaleEffect(1.2)
                        .tint(.blue)
                    
                    VStack(spacing: 8) {
                        Text("Loading League Forecast")
                            .font(.headline)
                        
                        Text("Getting latest league data...")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if let errorMessage = eplService.errorMessage {
                VStack(spacing: 20) {
                    Image(systemName: "exclamationmark.triangle")
                        .font(.largeTitle)
                        .foregroundColor(.orange)
                    
                    Text("Error")
                        .font(.headline)
                    
                    Text(errorMessage)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                    
                    Button("Retry") {
                        eplService.refreshData()
                    }
                    .buttonStyle(.bordered)
                }
                .padding()
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                VStack(spacing: 0) {
                    // Toggle between Forecast and Live views
                    HStack {
                        Spacer()
                        
                        HStack(spacing: 0) {
                            Button("Forecast") {
                                withAnimation(.easeInOut(duration: 0.5)) {
                                    showForecast = true
                                }
                            }
                            .font(.subheadline)
                            .fontWeight(.medium)
                            .foregroundColor(showForecast ? .white : .blue)
                            .frame(width: 75, height: 32)
                            .background(
                                RoundedRectangle(cornerRadius: 16)
                                    .fill(showForecast ? .blue : .clear)
                            )
                            
                            Button("Live") {
                                withAnimation(.easeInOut(duration: 0.5)) {
                                    showForecast = false
                                }
                            }
                            .font(.subheadline)
                            .fontWeight(.medium)
                            .foregroundColor(!showForecast ? .white : .blue)
                            .frame(width: 75, height: 32)
                            .background(
                                RoundedRectangle(cornerRadius: 16)
                                    .fill(!showForecast ? .blue : .clear)
                            )
                        }
                        .overlay(
                            RoundedRectangle(cornerRadius: 16)
                                .stroke(.blue, lineWidth: 1)
                        )
                        
                        Spacer()
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 8)
                    
                    ScrollViewReader { proxy in
                        ScrollView {
                        VStack(spacing: 4) {
                            ForEach(Array(sortedTeams.enumerated()), id: \.element.id) { index, team in
                                VStack(spacing: 0) {
                                    TeamRowView(
                                        team: team,
                                        isFavorite: team.name == userSettings.favoriteTeam,
                                        position: index + 1,
                                        showForecast: showForecast,
                                        contextualPPG: getContextualPPG(for: team)
                                    )
                                    .id("team-\(index)")
                                    
                                    // Add divider lines for Champions League and relegation zones
                                    if index == 3 { // After 4th place (Champions League)
                                        HStack {
                                            Rectangle()
                                                .fill(Color.blue)
                                                .frame(height: 2)
                                            Text("Champions League")
                                                .font(.caption2)
                                                .foregroundColor(.blue)
                                                .padding(.horizontal, 8)
                                            Rectangle()
                                                .fill(Color.blue)
                                                .frame(height: 2)
                                        }
                                        .padding(.vertical, 4)
                                    } else if index == eplService.teams.count - 4 { // Before last 3 (relegation zone)
                                        HStack {
                                            Rectangle()
                                                .fill(Color.red)
                                                .frame(height: 2)
                                            Text("Relegation Zone")
                                                .font(.caption2)
                                                .foregroundColor(.red)
                                                .padding(.horizontal, 8)
                                            Rectangle()
                                                .fill(Color.red)
                                                .frame(height: 2)
                                        }
                                        .padding(.vertical, 4)
                                    }
                                }
                            }
                        }
                    }
                    .refreshable {
                        // Track user-initiated refresh
                        NewRelic.recordCustomEvent("UserRefresh", attributes: [
                            "refreshTime": Date().timeIntervalSince1970,
                            "teamsCount": eplService.teams.count
                        ])
                        eplService.refreshData()
                    }
                    .onAppear {
                        print("📱 ScrollView appeared - teams count: \(eplService.teams.count)")
                        
                        // Go back to the EXACT approach that worked, with LazyVStack fix
                        if let favoriteTeam = userSettings.favoriteTeam,
                           let favoriteIndex = sortedTeams.firstIndex(where: { $0.name == favoriteTeam }) {
                            print("🎯 Found favorite team '\(favoriteTeam)' at index \(favoriteIndex)")
                            
                            // With VStack, all teams render immediately
                            DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
                                print("🧪 WORKING TEST - scrolling to team-\(favoriteIndex)")
                                proxy.scrollTo("team-\(favoriteIndex)", anchor: .center)
                            }
                        } else {
                            print("❌ No favorite team set or not found")
                        }
                    }
                    .onChange(of: sortedTeams) {
                        print("🔄 Teams data changed - count: \(sortedTeams.count)")
                        if !sortedTeams.isEmpty,
                           let favoriteTeam = userSettings.favoriteTeam,
                           let favoriteIndex = sortedTeams.firstIndex(where: { $0.name == favoriteTeam }) {
                            
                            DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
                                proxy.scrollTo("team-\(favoriteIndex)", anchor: .center)
                            }
                        }
                    }
                    .onChange(of: shouldResetScroll) { _, shouldReset in
                        if shouldReset {
                            print("🔄 Resetting scroll position after settings")
                            
                            if let favoriteTeam = userSettings.favoriteTeam,
                               let favoriteIndex = sortedTeams.firstIndex(where: { $0.name == favoriteTeam }) {
                                DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
                                    proxy.scrollTo("team-\(favoriteIndex)", anchor: .center)
                                }
                            }
                            shouldResetScroll = false
                        }
                    }
                    .onChange(of: showForecast) { _, _ in
                        // Add a slight delay for animation smoothness when switching views
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                            if let favoriteTeam = userSettings.favoriteTeam,
                               let favoriteIndex = sortedTeams.firstIndex(where: { $0.name == favoriteTeam }) {
                                withAnimation(.easeInOut(duration: 0.5)) {
                                    proxy.scrollTo("team-\(favoriteIndex)", anchor: .center)
                                }
                            }
                        }
                    }
                }
                }
            }
        }
        .onAppear {
            // Track table view appearance
            NewRelic.recordCustomEvent("TableViewAppeared", attributes: [
                "appearTime": Date().timeIntervalSince1970,
                "teamsLoaded": !eplService.teams.isEmpty
            ])
        }
    }
    
    private func scrollToFavoriteTeam(proxy: ScrollViewProxy) {
        print("🔍 DEBUG - Teams count: \(sortedTeams.count), Favorite: '\(userSettings.favoriteTeam ?? "nil")'")
        
        guard !sortedTeams.isEmpty, let favoriteTeam = userSettings.favoriteTeam else {
            print("❌ No teams or no favorite team set - Teams: \(sortedTeams.count), Favorite: \(userSettings.favoriteTeam ?? "nil")")
            return
        }
        
        print("🔍 Available teams: \(sortedTeams.map { $0.name })")
        
        guard let favoriteIndex = sortedTeams.firstIndex(where: { $0.name == favoriteTeam }) else {
            print("❌ Favorite team '\(favoriteTeam)' not found in teams list")
            print("🔍 Available teams: \(sortedTeams.map { $0.name })")
            return
        }
        
        let position = favoriteIndex + 1
        let totalTeams = sortedTeams.count
        
        print("🎯 FAVORITE TEAM SCROLL - '\(favoriteTeam)' at position \(position) of \(totalTeams)")
        
        // EPLF-25 Logic: Smart positioning based on team position
        let shouldScroll: Bool
        
        if position <= 4 {
            // Top 4 (Champions League) - stay at top, don't scroll
            shouldScroll = false
            print("🏆 Champions League position (\(position)) - staying at top")
        } else {
            // All other positions (5-20) - center on screen using .center anchor
            shouldScroll = true
            if position >= 17 {
                print("⚠️ Relegation zone position (\(position)) - centering on screen")
            } else {
                print("🎯 Mid-table position (\(position)) - centering on screen")
            }
        }
        
        if shouldScroll {
            // Simple approach using .center anchor that we know works
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                print("⚡ Scrolling to team-\(favoriteIndex) with .center anchor")
                withAnimation(.easeInOut(duration: 0.5)) {
                    proxy.scrollTo("team-\(favoriteIndex)", anchor: .center)
                }
            }
        }
    }
}

struct TeamRowView: View {
    let team: Team
    let isFavorite: Bool
    let position: Int
    let showForecast: Bool
    let contextualPPG: (value: String, label: String)

    var body: some View {
        HStack {
            // Position indicator with Champions League and relegation colors
            HStack(spacing: 4) {
                // League position indicator
                Circle()
                    .fill(positionIndicatorColor)
                    .frame(width: 8, height: 8)
            }

            Text("\(showForecast ? team.forecastedPosition : team.currentPosition)")
                .font(.title3)
                .fontWeight(.bold)
                .foregroundColor(isFavorite ? team.primaryColor : positionTextColor)
                .frame(width: 30, alignment: .leading)
                .accessibilityLabel("Position \(showForecast ? team.forecastedPosition : team.currentPosition)")

            VStack(alignment: .leading, spacing: 2) {
                Text(team.name)
                    .font(.body)
                    .fontWeight(isFavorite ? .semibold : .medium)
                    .foregroundColor(isFavorite ? team.primaryColor : .primary)

                Text("\(team.played) GP | \(team.points) PTS | \(contextualPPG.label): \(contextualPPG.value)")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 2) {
                Text("\(showForecast ? String(format: "%.2f", team.pointsPerGame) : String(team.points))")
                    .font(.title3)
                    .fontWeight(.bold)
                    .foregroundColor(isFavorite ? team.primaryColor : .primary)

                Text(showForecast ? "PPG" : "pts")
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
        }
        .padding(.vertical, 12)
        .padding(.horizontal, 16)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(isFavorite ? team.backgroundColor : Color.clear)
        )
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(team.name)\(isFavorite ? " (your team)" : ""), position \(showForecast ? team.forecastedPosition : team.currentPosition), \(showForecast ? "\(String(format: "%.2f", team.pointsPerGame)) points per game" : "\(team.points) current points"), played \(team.played) games, \(contextualPPG.label): \(contextualPPG.value)")
    }
    
    // Computed properties for position-based styling
    var displayPosition: Int {
        showForecast ? team.forecastedPosition : team.currentPosition
    }
    
    var positionIndicatorColor: Color {
        switch displayPosition {
        case 1...4:
            return .blue // Champions League
        case 18...20:
            return .red // Relegation
        default:
            return .gray // Mid-table
        }
    }
    
    var positionTextColor: Color {
        switch displayPosition {
        case 1...4:
            return .blue // Champions League
        case 18...20:
            return .red // Relegation
        default:
            return .primary // Mid-table
        }
    }
}




#Preview {
    NavigationView {
        TableView(shouldResetScroll: .constant(false))
            .navigationTitle("League Forecast")
    }
}