import SwiftUI
import NewRelic

struct SettingsView: View {
    @ObservedObject private var userSettings = UserSettings.shared
    @StateObject private var eplService = EPLService()
    @Environment(\.dismiss) private var dismiss
    @State private var showingTeamSelection = false
    
    var body: some View {
        NavigationView {
            List {
                Section("Favorite Team") {
                    if let favoriteTeam = userSettings.favoriteTeam {
                        HStack {
                            AsyncImage(url: URL(string: teamLogoURL(for: favoriteTeam))) { image in
                                image
                                    .resizable()
                                    .aspectRatio(contentMode: .fit)
                            } placeholder: {
                                Image(systemName: teamIcon(for: favoriteTeam))
                                    .foregroundColor(teamColorForName(favoriteTeam))
                            }
                            .frame(width: 24, height: 24)
                            
                            Text(favoriteTeam)
                            
                            Spacer()
                            
                            if let team = eplService.teams.first(where: { $0.name == favoriteTeam }) {
                                VStack(alignment: .trailing, spacing: 2) {
                                    Text("#\(team.forecastedPosition)")
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                    Text("\(String(format: "%.0f", team.forecastedPoints)) pts")
                                        .font(.caption2)
                                        .foregroundColor(.secondary)
                                }
                            }
                        }
                        .contentShape(Rectangle())
                        .onTapGesture {
                            showingTeamSelection = true
                        }
                    } else {
                        Button("Choose Favorite Team") {
                            showingTeamSelection = true
                        }
                    }
                }
                
                Section("About") {
                    HStack {
                        Text("Version")
                        Spacer()
                        Text(Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0")
                            .foregroundColor(.secondary)
                    }
                    
                    HStack {
                        Text("Build")
                        Spacer()
                        Text(Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "1")
                            .foregroundColor(.secondary)
                    }
                }
                
                Section {
                    Text("Data updates every 2 minutes during live matches and twice daily otherwise. Forecasts are based on current points per game projected to a full 38-game season.")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
        .sheet(isPresented: $showingTeamSelection) {
            FavoriteTeamSelectionView(isOnboarding: false)
        }
        .onAppear {
            // Track settings view appearance
            NewRelic.recordCustomEvent("SettingsViewAppeared", attributes: [
                "hasFavoriteTeam": userSettings.favoriteTeam != nil
            ])
        }
    }
    
    private func teamColorForName(_ teamName: String) -> Color {
        // Create a temporary team object to get color
        let dummyTeam = Team(
            name: teamName,
            played: 0, won: 0, drawn: 0, lost: 0, goalsFor: 0, against: 0,
            goalDifference: 0, points: 0, pointsPerGame: 0, forecastedPoints: 0,
            currentPosition: 0, forecastedPosition: 0
        )
        return dummyTeam.primaryColor
    }
}

#Preview {
    SettingsView()
}