import SwiftUI
import NewRelic

struct TableView: View {
    @StateObject private var eplService = EPLService()
    @ObservedObject private var userSettings = UserSettings.shared
    @State private var scrollPosition: String?
    @Binding var shouldResetScroll: Bool
    
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
                ScrollViewReader { proxy in
                    ScrollView {
                        VStack(spacing: 4) {
                            ForEach(Array(eplService.teams.enumerated()), id: \.element.id) { index, team in
                                VStack(spacing: 0) {
                                    TeamRowView(
                                        team: team,
                                        isFavorite: team.name == userSettings.favoriteTeam,
                                        position: index + 1
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
                           let favoriteIndex = eplService.teams.firstIndex(where: { $0.name == favoriteTeam }) {
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
                    .onChange(of: eplService.teams) {
                        print("🔄 Teams data changed - count: \(eplService.teams.count)")
                        if !eplService.teams.isEmpty,
                           let favoriteTeam = userSettings.favoriteTeam,
                           let favoriteIndex = eplService.teams.firstIndex(where: { $0.name == favoriteTeam }) {
                            
                            DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
                                proxy.scrollTo("team-\(favoriteIndex)", anchor: .center)
                            }
                        }
                    }
                    .onChange(of: shouldResetScroll) { _, shouldReset in
                        if shouldReset {
                            print("🔄 Resetting scroll position after settings")
                            
                            if let favoriteTeam = userSettings.favoriteTeam,
                               let favoriteIndex = eplService.teams.firstIndex(where: { $0.name == favoriteTeam }) {
                                DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
                                    proxy.scrollTo("team-\(favoriteIndex)", anchor: .center)
                                }
                            }
                            shouldResetScroll = false
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
        print("🔍 DEBUG - Teams count: \(eplService.teams.count), Favorite: '\(userSettings.favoriteTeam ?? "nil")'")
        
        guard !eplService.teams.isEmpty, let favoriteTeam = userSettings.favoriteTeam else {
            print("❌ No teams or no favorite team set - Teams: \(eplService.teams.count), Favorite: \(userSettings.favoriteTeam ?? "nil")")
            return
        }
        
        print("🔍 Available teams: \(eplService.teams.map { $0.name })")
        
        guard let favoriteIndex = eplService.teams.firstIndex(where: { $0.name == favoriteTeam }) else {
            print("❌ Favorite team '\(favoriteTeam)' not found in teams list")
            print("🔍 Available teams: \(eplService.teams.map { $0.name })")
            return
        }
        
        let position = favoriteIndex + 1
        let totalTeams = eplService.teams.count
        
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
    
    var body: some View {
        HStack {
            // Position indicator with Champions League and relegation colors
            HStack(spacing: 4) {
                // League position indicator
                Circle()
                    .fill(positionIndicatorColor)
                    .frame(width: 8, height: 8)
            }
            
            Text("\(team.forecastedPosition)")
                .font(.title3)
                .fontWeight(.bold)
                .foregroundColor(isFavorite ? team.primaryColor : positionTextColor)
                .frame(width: 30, alignment: .leading)
                .accessibilityLabel("Position \(team.forecastedPosition)")
            
            VStack(alignment: .leading, spacing: 2) {
                Text(team.name)
                    .font(.body)
                    .fontWeight(isFavorite ? .semibold : .medium)
                    .foregroundColor(isFavorite ? team.primaryColor : .primary)
                
                Text("\(team.played) GP | \(team.points) PTS | \(String(format: "%.1f", team.pointsPerGame)) PPG")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            VStack(alignment: .trailing, spacing: 2) {
                Text("\(String(format: "%.0f", team.forecastedPoints))")
                    .font(.title3)
                    .fontWeight(.bold)
                    .foregroundColor(isFavorite ? team.primaryColor : .primary)
                
                Text("pts")
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
        .accessibilityLabel("\(team.name)\(isFavorite ? " (your team)" : ""), position \(team.forecastedPosition), forecasted \(String(format: "%.0f", team.forecastedPoints)) points, played \(team.played) games, \(String(format: "%.1f", team.pointsPerGame)) points per game")
    }
    
    // Computed properties for position-based styling
    var positionIndicatorColor: Color {
        switch position {
        case 1...4:
            return .blue // Champions League
        case 18...20:
            return .red // Relegation
        default:
            return .gray // Mid-table
        }
    }
    
    var positionTextColor: Color {
        switch position {
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